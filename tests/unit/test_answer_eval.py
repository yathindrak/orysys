from pathlib import Path

import pytest

from orysys.evals.answers import evaluate, load_dataset


@pytest.mark.asyncio
async def test_grounded_answer_dataset_matches_expected_behavior() -> None:
    dataset = load_dataset(Path("evals/datasets/grounded-answers-v1.json"))

    report = await evaluate(dataset)

    assert report["judge_profile"] == "deterministic-only"
    assert report["passed"] == report["total"] == 3
