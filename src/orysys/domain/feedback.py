from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class FeedbackStatus(StrEnum):
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"


class FeedbackItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    feedback_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    owner_subject: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    trace_id: str | None = None
    rating: int = Field(ge=-1, le=1)
    note: str | None = Field(default=None, max_length=2_000)
    prompt_version: str = Field(min_length=1)
    model: str = Field(min_length=1)
    corpus_version: str = Field(min_length=1)
    route: str = Field(min_length=1)
    status: FeedbackStatus = FeedbackStatus.SUBMITTED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reviewed_at: datetime | None = None
