import asyncio
import math
import time

import httpx2
from redis.asyncio import Redis

from orysys.domain.errors import RateLimitUnavailable
from orysys.domain.security import RateLimitDecision

_TOKEN_BUCKET_LUA = """
local current = redis.call('HMGET', KEYS[1], 'tokens', 'updated')
local tokens = tonumber(current[1]) or tonumber(ARGV[2])
local updated = tonumber(current[2]) or tonumber(ARGV[1])
local now = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local refill = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])
tokens = math.min(capacity, tokens + math.max(0, now - updated) * refill / 1000)
local allowed = 0
local retry = 0
if tokens >= cost then
  tokens = tokens - cost
  allowed = 1
else
  retry = math.ceil((cost - tokens) / refill)
end
redis.call('HSET', KEYS[1], 'tokens', tokens, 'updated', now)
redis.call('PEXPIRE', KEYS[1], math.ceil(capacity / refill * 1000 * 2))
return {allowed, retry, tostring(tokens)}
"""


class InMemoryRateLimiter:
    def __init__(self, *, capacity: int, refill_per_second: float) -> None:
        self._capacity = float(capacity)
        self._refill = refill_per_second
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = asyncio.Lock()

    async def consume(self, subject: str, cost: int = 1) -> RateLimitDecision:
        now = time.monotonic()
        async with self._lock:
            tokens, updated = self._buckets.get(subject, (self._capacity, now))
            tokens = min(self._capacity, tokens + (now - updated) * self._refill)
            if tokens >= cost:
                tokens -= cost
                self._buckets[subject] = (tokens, now)
                return RateLimitDecision(allowed=True, remaining=tokens)
            self._buckets[subject] = (tokens, now)
        retry = max(1, math.ceil((cost - tokens) / self._refill))
        return RateLimitDecision(allowed=False, retry_after_seconds=retry, remaining=tokens)


class UpstashRateLimiter:
    def __init__(
        self,
        *,
        url: str,
        token: str,
        capacity: int,
        refill_per_second: float,
        client: httpx2.AsyncClient | None = None,
    ) -> None:
        self._capacity = capacity
        self._refill = refill_per_second
        self._client = client or httpx2.AsyncClient(
            base_url=url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
        self._owns_client = client is None

    async def consume(self, subject: str, cost: int = 1) -> RateLimitDecision:
        try:
            response = await self._client.post(
                "/",
                json=[
                    "EVAL",
                    _TOKEN_BUCKET_LUA,
                    "1",
                    f"orysys:rate:{subject}",
                    str(int(time.time() * 1000)),
                    str(self._capacity),
                    str(self._refill),
                    str(cost),
                ],
            )
            response.raise_for_status()
            result = response.json()["result"]
            return RateLimitDecision(
                allowed=int(result[0]) == 1,
                retry_after_seconds=max(1, math.ceil(float(result[1])))
                if int(result[0]) == 0
                else None,
                remaining=max(0.0, float(result[2])),
            )
        except (httpx2.HTTPError, KeyError, TypeError, ValueError, IndexError) as error:
            raise RateLimitUnavailable from error

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()


class RedisRateLimiter:
    def __init__(
        self,
        *,
        url: str,
        capacity: int,
        refill_per_second: float,
    ) -> None:
        self._capacity = capacity
        self._refill = refill_per_second
        self._client = Redis.from_url(url, decode_responses=True)

    async def consume(self, subject: str, cost: int = 1) -> RateLimitDecision:
        try:
            result = await self._client.eval(
                _TOKEN_BUCKET_LUA,
                1,
                f"orysys:rate:{subject}",
                str(int(time.time() * 1000)),
                str(self._capacity),
                str(self._refill),
                str(cost),
            )
            if not isinstance(result, list) or len(result) != 3:
                raise ValueError("unexpected Redis rate-limit response")
            return RateLimitDecision(
                allowed=int(result[0]) == 1,
                retry_after_seconds=max(1, math.ceil(float(result[1])))
                if int(result[0]) == 0
                else None,
                remaining=max(0.0, float(result[2])),
            )
        except Exception as error:
            raise RateLimitUnavailable from error

    async def close(self) -> None:
        await self._client.aclose()
