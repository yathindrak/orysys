import argparse
import asyncio
import json
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from orysys.adapters.cloudflare.chat import CloudflareChatModel
from orysys.config import Settings
from orysys.domain.evidence import GroundedAnswer
from orysys.domain.validation import validate_answer_citations
from orysys.ports.models import ChatModel, MessageRole, ModelMessage, ModelRequest


class AnswerEvaluationCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    answer: GroundedAnswer
    authorized_evidence_ids: frozenset[str]
    evidence_excerpts: tuple[str, ...] = ()
    required_terms: tuple[str, ...] = ()
    expected_behavior: Literal["grounded", "safe_insufficient", "reject"]
    judge: bool = False


class AnswerEvaluationDataset(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = Field(min_length=1)
    cases: tuple[AnswerEvaluationCase, ...] = Field(min_length=1)


class JudgeVerdict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    grounded: bool
    relevant: bool
    professional: bool
    reason: str = Field(min_length=1, max_length=500)


def load_dataset(path: Path) -> AnswerEvaluationDataset:
    return TypeAdapter(AnswerEvaluationDataset).validate_json(path.read_text(encoding="utf-8"))


def classify(case: AnswerEvaluationCase) -> Literal["grounded", "safe_insufficient", "reject"]:
    answer = case.answer
    if answer.incomplete and not answer.claims and "insufficient" in answer.summary.casefold():
        return "safe_insufficient"

    validations = validate_answer_citations(
        tuple(claim.evidence_ids for claim in answer.claims),
        set(case.authorized_evidence_ids),
    )
    rendered = " ".join((answer.summary, *(claim.text for claim in answer.claims))).casefold()
    terms_present = all(term.casefold() in rendered for term in case.required_terms)
    if validations and all(result.passed for result in validations) and terms_present:
        return "grounded"
    return "reject"


async def _judge(case: AnswerEvaluationCase, model: ChatModel) -> JudgeVerdict:
    payload = {
        "question": case.question,
        "answer": case.answer.model_dump(mode="json"),
        "authorized_evidence": case.evidence_excerpts,
    }
    result = await model.complete(
        ModelRequest(
            messages=(
                ModelMessage(
                    role=MessageRole.SYSTEM,
                    content=(
                        "Independently evaluate the synthetic answer only against the supplied "
                        "evidence. Return JSON. Grounded means every factual claim is supported; "
                        "relevant means it answers the question; professional means it avoids "
                        "unsupported commitments or financial advice."
                    ),
                ),
                ModelMessage(role=MessageRole.USER, content=json.dumps(payload, sort_keys=True)),
            ),
            response_schema=cast(dict[str, object], JudgeVerdict.model_json_schema()),
            max_tokens=500,
        )
    )
    return JudgeVerdict.model_validate_json(result.text)


async def evaluate(
    dataset: AnswerEvaluationDataset,
    judge_model: ChatModel | None = None,
) -> dict[str, object]:
    cases: list[dict[str, object]] = []
    for case in dataset.cases:
        actual = classify(case)
        row: dict[str, object] = {
            "id": case.id,
            "expected_behavior": case.expected_behavior,
            "actual_behavior": actual,
            "passed": actual == case.expected_behavior,
        }
        if case.judge and judge_model is not None and actual == "grounded":
            verdict = await _judge(case, judge_model)
            row["judge"] = verdict.model_dump(mode="json")
            row["passed"] = bool(row["passed"]) and all(
                (verdict.grounded, verdict.relevant, verdict.professional)
            )
        cases.append(row)
    return {
        "suite": dataset.version,
        "judge_profile": "live-selective" if judge_model is not None else "deterministic-only",
        "passed": sum(bool(case["passed"]) for case in cases),
        "total": len(cases),
        "cases": cases,
    }


async def run(dataset_path: Path, live_judge: bool) -> dict[str, object]:
    dataset = load_dataset(dataset_path)
    if not live_judge:
        report = await evaluate(dataset)
        report["judge_model"] = None
        return report

    settings = Settings()
    settings.require_chat_credentials()
    assert settings.cloudflare_account_id is not None
    assert settings.cloudflare_api_token is not None
    model = CloudflareChatModel(
        account_id=settings.cloudflare_account_id,
        api_token=settings.cloudflare_api_token.get_secret_value(),
        model=settings.cloudflare_eval_model,
        max_tokens=500,
        gateway_id=settings.cloudflare_ai_gateway_id,
        max_concurrency=1,
        retry_attempts=settings.provider_retry_attempts,
    )
    try:
        report = await evaluate(dataset, model)
        report["judge_model"] = settings.cloudflare_eval_model
        return report
    finally:
        await model.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate grounded-answer behavior")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evals/datasets/grounded-answers-v1.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    parser.add_argument("--live-judge", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(run(args.dataset, args.live_judge))
    output = args.output or Path(
        "evals/results/grounded-answers-live-judge-v1.json"
        if args.live_judge
        else "evals/results/grounded-answers-v1.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(f"{json.dumps(report, indent=2, sort_keys=True)}\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    if report["passed"] != report["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
