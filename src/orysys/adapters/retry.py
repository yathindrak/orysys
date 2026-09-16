import asyncio
from collections.abc import Awaitable, Callable

import httpx2

_TRANSIENT_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})


async def request_with_retry(
    operation: Callable[[], Awaitable[httpx2.Response]],
    *,
    max_attempts: int,
    base_delay_seconds: float = 0.1,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> httpx2.Response:
    """Retry only transient, idempotent provider requests with bounded backoff."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least one")
    for attempt in range(1, max_attempts + 1):
        try:
            response = await operation()
            response.raise_for_status()
            return response
        except httpx2.HTTPStatusError as error:
            if error.response.status_code not in _TRANSIENT_STATUS_CODES or attempt == max_attempts:
                raise
            delay = _retry_delay(error.response, attempt, base_delay_seconds)
        except httpx2.RequestError:
            if attempt == max_attempts:
                raise
            delay = base_delay_seconds * (2 ** (attempt - 1))
        await sleep(delay)
    raise AssertionError("retry loop exhausted without returning or raising")


def _retry_delay(response: httpx2.Response, attempt: int, base_delay_seconds: float) -> float:
    retry_after = response.headers.get("retry-after")
    if retry_after is not None:
        try:
            return min(2.0, max(0.0, float(retry_after)))
        except ValueError:
            pass
    return min(2.0, base_delay_seconds * (2.0 ** (attempt - 1)))
