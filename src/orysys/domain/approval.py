from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class ApprovalProposal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    proposal_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    requester_subject: str = Field(min_length=1)
    action: str = Field(min_length=1)
    target: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=500)
    action_hash: str = Field(min_length=64, max_length=64)
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime
    decided_at: datetime | None = None
    executed_at: datetime | None = None


class ApprovalTicket(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    proposal: ApprovalProposal
    approval_token: str = Field(min_length=32)
