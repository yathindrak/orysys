from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from orysys.domain.evidence import Evidence


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(min_length=1, max_length=120)
    statement: str = Field(min_length=1, max_length=1_000)
    evidence_ids: tuple[str, ...] = Field(min_length=1)


class ResearchBatch(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    batch_id: str = Field(min_length=1)
    evidence: tuple[Evidence, ...] = Field(min_length=1)
    attempt: int = Field(default=0, ge=0, le=1)


class WorkerStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"


class WorkerOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    batch_id: str
    attempt: int = Field(ge=0, le=1)
    status: WorkerStatus
    findings: tuple[Finding, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    public_error: str | None = None
