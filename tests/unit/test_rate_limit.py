import pytest

from orysys.adapters.rate_limit import InMemoryRateLimiter


@pytest.mark.asyncio
async def test_token_bucket_limits_each_subject_independently() -> None:
    limiter = InMemoryRateLimiter(capacity=2, refill_per_second=0.001)

    assert (await limiter.consume("tenant:user-a")).allowed
    assert (await limiter.consume("tenant:user-a")).allowed
    denied = await limiter.consume("tenant:user-a")
    other_user = await limiter.consume("tenant:user-b")

    assert not denied.allowed
    assert denied.retry_after_seconds is not None
    assert other_user.allowed
