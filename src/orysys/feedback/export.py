import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from langsmith import Client

from orysys.adapters.postgres_controls import PostgresFeedbackRepository
from orysys.config import Settings
from orysys.domain.feedback import FeedbackItem


def dataset_example(item: FeedbackItem) -> dict[str, Any]:
    """Project a reviewed item without tenant or user identifiers."""
    return {
        "inputs": {
            "run_id": item.run_id,
            "trace_id": item.trace_id,
            "route": item.route,
        },
        "outputs": {
            "rating": item.rating,
            "note": item.note,
        },
        "metadata": {
            "feedback_id": item.feedback_id,
            "prompt_version": item.prompt_version,
            "model": item.model,
            "corpus_version": item.corpus_version,
            "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
        },
    }


async def export_reviewed(
    output: Path,
    *,
    dataset_name: str | None = None,
) -> int:
    settings = Settings()
    if settings.database_url is None:
        raise ValueError("DATABASE_URL is required")
    repository = PostgresFeedbackRepository(settings.database_url.get_secret_value())
    examples = [dataset_example(item) for item in await repository.reviewed()]
    await asyncio.to_thread(
        _write_jsonl,
        output,
        examples,
    )
    if dataset_name is not None and examples:
        if settings.langsmith_api_key is None:
            raise ValueError("LANGSMITH_API_KEY is required for LangSmith export")
        await asyncio.to_thread(
            _upload_langsmith,
            settings.langsmith_api_key.get_secret_value(),
            dataset_name,
            examples,
        )
    return len(examples)


def _write_jsonl(output: Path, examples: list[dict[str, Any]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(f"{json.dumps(example, sort_keys=True)}\n" for example in examples),
        encoding="utf-8",
    )


def _upload_langsmith(
    api_key: str,
    dataset_name: str,
    examples: list[dict[str, Any]],
) -> None:
    client = Client(api_key=api_key)
    dataset = client.create_dataset(
        dataset_name,
        description="Human-reviewed Orysys feedback. Never populated automatically.",
    )
    client.create_examples(dataset_id=dataset.id, examples=examples)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export reviewed feedback to JSONL")
    parser.add_argument("--output", type=Path, default=Path("evals/reviewed-feedback.jsonl"))
    parser.add_argument("--langsmith-dataset")
    args = parser.parse_args()
    count = asyncio.run(export_reviewed(args.output, dataset_name=args.langsmith_dataset))
    print(f"Exported {count} reviewed feedback examples to {args.output}")


if __name__ == "__main__":
    main()
