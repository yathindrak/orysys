import httpx2
import pytest

from orysys.adapters.retry import request_with_retry


@pytest.mark.asyncio
async def test_retry_uses_bounded_backoff_for_transient_5xx() -> None:
    attempts = 0
    delays: list[float] = []
    request = httpx2.Request("POST", "https://provider.example/v1")

    async def operation() -> httpx2.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx2.Response(500, request=request)
        return httpx2.Response(200, request=request)

    async def sleep(delay: float) -> None:
        delays.append(delay)

    response = await request_with_retry(
        operation,
        max_attempts=3,
        base_delay_seconds=0.01,
        sleep=sleep,
    )

    assert response.status_code == 200
    assert attempts == 3
    assert delays == [0.01, 0.02]


@pytest.mark.asyncio
async def test_retry_recovers_from_network_timeout() -> None:
    attempts = 0
    request = httpx2.Request("POST", "https://provider.example/v1")

    async def operation() -> httpx2.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx2.ReadTimeout("timed out", request=request)
        return httpx2.Response(200, request=request)

    async def no_wait(delay: float) -> None:
        del delay

    response = await request_with_retry(operation, max_attempts=2, sleep=no_wait)

    assert response.status_code == 200
    assert attempts == 2
