from datetime import UTC, datetime

from orysys.domain.feedback import FeedbackItem, FeedbackStatus
from orysys.feedback.export import dataset_example


def test_dataset_projection_excludes_identity_and_preserves_versions() -> None:
    item = FeedbackItem(
        feedback_id="feedback-1",
        tenant_id="secret-tenant",
        owner_subject="secret-user",
        run_id="run-1",
        trace_id="trace-1",
        rating=1,
        note="useful",
        prompt_version="prompt-v1",
        model="model-v1",
        corpus_version="corpus-v1",
        route="direct",
        status=FeedbackStatus.REVIEWED,
        reviewed_at=datetime(2026, 9, 16, tzinfo=UTC),
    )

    example = dataset_example(item)
    serialized = str(example)

    assert "secret-tenant" not in serialized
    assert "secret-user" not in serialized
    assert example["metadata"]["prompt_version"] == "prompt-v1"
