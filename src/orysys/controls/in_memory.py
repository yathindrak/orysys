import asyncio
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from orysys.domain.approval import ApprovalProposal, ApprovalStatus, ApprovalTicket
from orysys.domain.errors import AuthorizationDenied, OrysysError, ResourceNotFound
from orysys.domain.feedback import FeedbackItem, FeedbackStatus
from orysys.domain.identity import Principal, Role
from orysys.domain.memory import AuditEvent


class InMemoryApprovalRepository:
    def __init__(self) -> None:
        self._items: dict[str, tuple[ApprovalProposal, str]] = {}
        self._lock = asyncio.Lock()
        self.audit_events: list[AuditEvent] = []

    async def propose(
        self, principal: Principal, *, action: str, target: str, reason: str
    ) -> ApprovalTicket:
        _require_admin(principal)
        if action != "simulate_service_restart":
            raise OrysysError("unsupported_action", "The requested action is not supported.")
        token = secrets.token_urlsafe(32)
        proposal = ApprovalProposal(
            proposal_id=str(uuid4()),
            tenant_id=principal.tenant_id,
            requester_subject=principal.subject,
            action=action,
            target=target,
            reason=reason,
            action_hash=_action_hash(action, target, reason),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        async with self._lock:
            self._items[proposal.proposal_id] = (proposal, _token_hash(token))
            self.audit_events.append(
                _approval_audit(proposal, principal, "approval.proposed", "pending")
            )
        return ApprovalTicket(proposal=proposal, approval_token=token)

    async def decide(
        self,
        proposal_id: str,
        principal: Principal,
        *,
        approval_token: str,
        confirm: bool,
    ) -> ApprovalProposal:
        _require_admin(principal)
        async with self._lock:
            stored = self._items.get(proposal_id)
            if stored is None:
                raise ResourceNotFound("approval proposal")
            proposal, token_hash = stored
            _validate_proposal(proposal, principal, approval_token, token_hash)
            now = datetime.now(UTC)
            status = ApprovalStatus.APPROVED if confirm else ApprovalStatus.DENIED
            proposal = proposal.model_copy(
                update={
                    "status": status,
                    "decided_at": now,
                    "executed_at": now if confirm else None,
                }
            )
            self._items[proposal_id] = (proposal, token_hash)
            self.audit_events.append(
                _approval_audit(
                    proposal,
                    principal,
                    "approval.approved" if confirm else "approval.denied",
                    status.value,
                )
            )
            return proposal


class InMemoryFeedbackRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str, str], FeedbackItem] = {}
        self._lock = asyncio.Lock()

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
    ) -> FeedbackItem:
        key = (principal.tenant_id, principal.subject, run_id)
        async with self._lock:
            existing = self._items.get(key)
            if existing is not None:
                return existing
            item = FeedbackItem(
                feedback_id=str(uuid4()),
                tenant_id=principal.tenant_id,
                owner_subject=principal.subject,
                run_id=run_id,
                trace_id=trace_id,
                rating=rating,
                note=note,
                prompt_version=prompt_version,
                model=model,
                corpus_version=corpus_version,
                route=route,
            )
            self._items[key] = item
            return item

    async def mark_reviewed(self, feedback_id: str, principal: Principal) -> FeedbackItem:
        _require_admin(principal)
        async with self._lock:
            match = next(
                (item for item in self._items.values() if item.feedback_id == feedback_id),
                None,
            )
            if match is None or match.tenant_id != principal.tenant_id:
                raise ResourceNotFound("feedback")
            reviewed = match.model_copy(
                update={"status": FeedbackStatus.REVIEWED, "reviewed_at": datetime.now(UTC)}
            )
            self._items[(match.tenant_id, match.owner_subject, match.run_id)] = reviewed
            return reviewed

    async def reviewed(self, *, limit: int = 1_000) -> tuple[FeedbackItem, ...]:
        async with self._lock:
            items = [
                item for item in self._items.values() if item.status is FeedbackStatus.REVIEWED
            ]
        return tuple(sorted(items, key=lambda item: item.created_at)[:limit])


def _require_admin(principal: Principal) -> None:
    if Role.ADMINISTRATOR not in principal.roles:
        raise AuthorizationDenied


def _action_hash(action: str, target: str, reason: str) -> str:
    payload = json.dumps(
        {"action": action, "target": target, "reason": reason},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _approval_audit(
    proposal: ApprovalProposal,
    principal: Principal,
    action: str,
    outcome: str,
) -> AuditEvent:
    return AuditEvent(
        audit_id=str(uuid4()),
        tenant_id=principal.tenant_id,
        actor_subject=principal.subject,
        action=action,
        resource_type="approval",
        resource_id=proposal.proposal_id,
        outcome=outcome,
    )


def _validate_proposal(
    proposal: ApprovalProposal,
    principal: Principal,
    token: str,
    expected_token_hash: str,
) -> None:
    if proposal.tenant_id != principal.tenant_id or proposal.requester_subject != principal.subject:
        raise ResourceNotFound("approval proposal")
    if proposal.status is not ApprovalStatus.PENDING:
        raise OrysysError("approval_replayed", "This approval has already been decided.")
    if proposal.expires_at <= datetime.now(UTC):
        raise OrysysError("approval_expired", "This approval has expired.")
    if not hmac.compare_digest(_token_hash(token), expected_token_hash):
        raise AuthorizationDenied
