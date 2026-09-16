import pytest

from orysys.evals.reliability import run_load_smoke


@pytest.mark.asyncio
async def test_local_load_smoke_has_no_failures() -> None:
    report = await run_load_smoke(request_count=12, concurrency=3)

    assert report["failures"] == 0
    assert report["request_count"] == 12
    assert report["provider_calls"] == 0
