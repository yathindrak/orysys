from datetime import datetime
from typing import Protocol

from orysys.domain.approval import ApprovalProposal, ApprovalTicket
from orysys.domain.feedback import FeedbackItem
from orysys.domain.identity import Principal
from orysys.domain.memory import AuditEvent, MemoryItem, MemoryKind


class MemoryRepository(Protocol):
    async def propose(
        self,
        principal: Principal,
        *,
        kind: MemoryKind,
        content: str,
        purpose: str,
        provenance_run_id: str,
        expires_at: datetime,
    ) -> MemoryItem: ...

    async def confirm(self, memory_id: str, principal: Principal) -> MemoryItem: ...

    async def recall(self, principal: Principal, *, limit: int = 20) -> tuple[MemoryItem, ...]: ...

    async def delete(self, memory_id: str, principal: Principal) -> None: ...


class AuditRepository(Protocol):
    async def record(self, event: AuditEvent) -> None: ...


class ApprovalRepository(Protocol):
    async def propose(
        self, principal: Principal, *, action: str, target: str, reason: str
    ) -> ApprovalTicket: ...

    async def decide(
        self,
        proposal_id: str,
        principal: Principal,
        *,
        approval_token: str,
        confirm: bool,
    ) -> ApprovalProposal: ...


class FeedbackRepository(Protocol):
    async def record(
        self,
        principal: Principal,
        *,
        run_id: str,
        trace_id: str | None,
        rating: int,
        note: str | None,
        prompt_version: str,
        model: str,
        corpus_version: str,
        route: str,
    ) -> FeedbackItem: ...

    async def mark_reviewed(self, feedback_id: str, principal: Principal) -> FeedbackItem: ...

    async def reviewed(self, *, limit: int = 1_000) -> tuple[FeedbackItem, ...]: ...
