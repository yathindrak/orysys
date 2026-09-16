from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EventType(StrEnum):
    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    NODE_STARTED = "node.started"
    NODE_COMPLETED = "node.completed"
    RETRIEVAL_STARTED = "retrieval.started"
    RETRIEVAL_COMPLETED = "retrieval.completed"
    RETRIEVAL_DEGRADED = "retrieval.degraded"
    RESEARCH_PLANNED = "research.planned"
    RESEARCH_BATCHES_COMPLETED = "research.batches_completed"
    RESEARCH_RECURSION = "research.recursion"
    TOOL_REQUESTED = "tool.requested"
    TOOL_COMPLETED = "tool.completed"
    TOOL_DENIED = "tool.denied"
    TOOL_FAILED = "tool.failed"
    VALIDATION_COMPLETED = "validation.completed"
    ANSWER_DELTA = "answer.delta"
    ANSWER_COMPLETED = "answer.completed"


class ActivityEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "1"
    sequence: int = Field(ge=0)
    request_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    type: EventType
    node: str | None = None
    public_payload: dict[str, object] = Field(default_factory=dict)
