import pytest

from orysys.evals.controls import evaluate


@pytest.mark.asyncio
async def test_deterministic_control_suite_passes() -> None:
    report = await evaluate()

    assert report["passed"] == report["total"]
