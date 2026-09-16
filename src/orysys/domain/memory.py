from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class MemoryKind(StrEnum):
    PREFERENCE = "preference"
    FACT = "fact"


class MemoryStatus(StrEnum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    DELETED = "deleted"


class MemoryItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    memory_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    owner_subject: str = Field(min_length=1)
    kind: MemoryKind
    content: str = Field(min_length=1, max_length=1_000)
    purpose: str = Field(min_length=1, max_length=500)
    provenance_run_id: str = Field(min_length=1)
    status: MemoryStatus = MemoryStatus.PROPOSED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime
    confirmed_at: datetime | None = None
    deleted_at: datetime | None = None


class AuditEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    audit_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    actor_subject: str = Field(min_length=1)
    action: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
