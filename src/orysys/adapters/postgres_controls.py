import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from orysys.adapters.postgres import PostgresAuditRepository
from orysys.controls.in_memory import _action_hash, _require_admin, _token_hash
from orysys.domain.approval import ApprovalProposal, ApprovalStatus, ApprovalTicket
from orysys.domain.errors import AuthorizationDenied, OrysysError, ResourceNotFound
from orysys.domain.feedback import FeedbackItem, FeedbackStatus
from orysys.domain.identity import Principal
from orysys.domain.memory import AuditEvent
from orysys.ports.persistence import AuditRepository


class PostgresApprovalRepository:
    def __init__(self, dsn: str, audit: AuditRepository | None = None) -> None:
        self._dsn = dsn
        self._audit = audit or PostgresAuditRepository(dsn)

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
        async with await psycopg.AsyncConnection.connect(self._dsn) as connection:
            await connection.execute(
                """INSERT INTO approval_proposals
                   (proposal_id, tenant_id, requester_subject, action, target, reason,
                    action_hash, token_hash, status, created_at, expires_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    proposal.proposal_id,
                    proposal.tenant_id,
                    proposal.requester_subject,
                    proposal.action,
                    proposal.target,
                    proposal.reason,
                    proposal.action_hash,
                    _token_hash(token),
                    proposal.status.value,
                    proposal.created_at,
                    proposal.expires_at,
                ),
            )
        await self._audit_event(proposal, principal, "approval.proposed", "pending")
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
        async with await psycopg.AsyncConnection.connect(
            self._dsn, row_factory=dict_row
        ) as connection:
            row = await (
                await connection.execute(
                    """SELECT * FROM approval_proposals
                       WHERE proposal_id = %s AND tenant_id = %s AND requester_subject = %s""",
                    (proposal_id, principal.tenant_id, principal.subject),
                )
            ).fetchone()
            if row is None:
                raise ResourceNotFound("approval proposal")
            proposal = _approval(row)
            if proposal.status is not ApprovalStatus.PENDING:
                raise OrysysError("approval_replayed", "This approval has already been decided.")
            if proposal.expires_at <= datetime.now(UTC):
                await connection.execute(
                    "UPDATE approval_proposals SET status = 'expired' WHERE proposal_id = %s",
                    (proposal_id,),
                )
                await connection.commit()
                raise OrysysError("approval_expired", "This approval has expired.")
            if not hmac.compare_digest(_token_hash(approval_token), row["token_hash"]):
                raise AuthorizationDenied
            expected_hash = _action_hash(proposal.action, proposal.target, proposal.reason)
            if not hmac.compare_digest(expected_hash, proposal.action_hash):
                raise AuthorizationDenied
            now = datetime.now(UTC)
            status = ApprovalStatus.APPROVED if confirm else ApprovalStatus.DENIED
            cursor = await connection.execute(
                """UPDATE approval_proposals
                   SET status = %s, decided_at = %s, executed_at = %s
                   WHERE proposal_id = %s AND status = 'pending'""",
                (status.value, now, now if confirm else None, proposal_id),
            )
            if cursor.rowcount != 1:
                raise OrysysError("approval_replayed", "This approval has already been decided.")
            proposal = proposal.model_copy(
                update={
                    "status": status,
                    "decided_at": now,
                    "executed_at": now if confirm else None,
                }
            )
        await self._audit_event(
            proposal,
            principal,
            "approval.approved" if confirm else "approval.denied",
            status.value,
        )
        return proposal

    async def _audit_event(
        self,
        proposal: ApprovalProposal,
        principal: Principal,
        action: str,
        outcome: str,
    ) -> None:
        await self._audit.record(
            AuditEvent(
                audit_id=str(uuid4()),
                tenant_id=principal.tenant_id,
                actor_subject=principal.subject,
                action=action,
                resource_type="approval",
                resource_id=proposal.proposal_id,
                outcome=outcome,
            )
        )


class PostgresFeedbackRepository:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

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
        async with await psycopg.AsyncConnection.connect(
            self._dsn, row_factory=dict_row
        ) as connection:
            row = await (
                await connection.execute(
                    """INSERT INTO feedback
                       (feedback_id, tenant_id, owner_subject, run_id, trace_id, rating,
                        note, prompt_version, model, corpus_version, route, status, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (tenant_id, owner_subject, run_id) DO UPDATE
                       SET run_id = EXCLUDED.run_id
                       RETURNING *""",
                    (
                        item.feedback_id,
                        item.tenant_id,
                        item.owner_subject,
                        item.run_id,
                        item.trace_id,
                        item.rating,
                        item.note,
                        item.prompt_version,
                        item.model,
                        item.corpus_version,
                        item.route,
                        item.status.value,
                        item.created_at,
                    ),
                )
            ).fetchone()
        assert row is not None
        return _feedback(row)

    async def mark_reviewed(self, feedback_id: str, principal: Principal) -> FeedbackItem:
        _require_admin(principal)
        now = datetime.now(UTC)
        async with await psycopg.AsyncConnection.connect(
            self._dsn, row_factory=dict_row
        ) as connection:
            row = await (
                await connection.execute(
                    """UPDATE feedback SET status = 'reviewed', reviewed_at = %s
                       WHERE feedback_id = %s AND tenant_id = %s RETURNING *""",
                    (now, feedback_id, principal.tenant_id),
                )
            ).fetchone()
        if row is None:
            raise ResourceNotFound("feedback")
        return _feedback(row)

    async def reviewed(self, *, limit: int = 1_000) -> tuple[FeedbackItem, ...]:
        async with await psycopg.AsyncConnection.connect(
            self._dsn, row_factory=dict_row
        ) as connection:
            rows = await (
                await connection.execute(
                    "SELECT * FROM feedback WHERE status = 'reviewed' ORDER BY created_at LIMIT %s",
                    (limit,),
                )
            ).fetchall()
        return tuple(_feedback(row) for row in rows)


def _approval(row: dict[str, Any]) -> ApprovalProposal:
    return ApprovalProposal(
        proposal_id=row["proposal_id"],
        tenant_id=row["tenant_id"],
        requester_subject=row["requester_subject"],
        action=row["action"],
        target=row["target"],
        reason=row["reason"],
        action_hash=row["action_hash"],
        status=ApprovalStatus(row["status"]),
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        decided_at=row["decided_at"],
        executed_at=row["executed_at"],
    )


def _feedback(row: dict[str, Any]) -> FeedbackItem:
    return FeedbackItem(
        feedback_id=row["feedback_id"],
        tenant_id=row["tenant_id"],
        owner_subject=row["owner_subject"],
        run_id=row["run_id"],
        trace_id=row["trace_id"],
        rating=row["rating"],
        note=row["note"],
        prompt_version=row["prompt_version"],
        model=row["model"],
        corpus_version=row["corpus_version"],
        route=row["route"],
        status=FeedbackStatus(row["status"]),
        created_at=row["created_at"],
        reviewed_at=row["reviewed_at"],
    )
