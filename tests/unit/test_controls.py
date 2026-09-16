from datetime import UTC, datetime, timedelta

import pytest

from orysys.controls.in_memory import (
    InMemoryApprovalRepository,
    InMemoryFeedbackRepository,
)
from orysys.domain.approval import ApprovalStatus
from orysys.domain.errors import AuthorizationDenied, OrysysError, ResourceNotFound
from orysys.domain.feedback import FeedbackStatus
from orysys.domain.identity import Principal, Role


def _principal(subject: str = "admin", role: Role = Role.ADMINISTRATOR) -> Principal:
    return Principal(subject=subject, tenant_id="tenant-1", roles=frozenset({role}))


@pytest.mark.asyncio
async def test_approval_is_identity_bound_one_time_and_audited() -> None:
    repository = InMemoryApprovalRepository()
    ticket = await repository.propose(
        _principal(),
        action="simulate_service_restart",
        target="search-api",
        reason="deploy",
    )

    with pytest.raises(ResourceNotFound):
        await repository.decide(
            ticket.proposal.proposal_id,
            _principal("other-admin"),
            approval_token=ticket.approval_token,
            confirm=True,
        )
    approved = await repository.decide(
        ticket.proposal.proposal_id,
        _principal(),
        approval_token=ticket.approval_token,
        confirm=True,
    )
    with pytest.raises(OrysysError, match="already been decided"):
        await repository.decide(
            ticket.proposal.proposal_id,
            _principal(),
            approval_token=ticket.approval_token,
            confirm=True,
        )

    assert approved.status is ApprovalStatus.APPROVED
    assert approved.executed_at is not None
    assert [event.action for event in repository.audit_events] == [
        "approval.proposed",
        "approval.approved",
    ]


@pytest.mark.asyncio
async def test_approval_denial_expiry_and_role_are_enforced() -> None:
    repository = InMemoryApprovalRepository()
    with pytest.raises(AuthorizationDenied):
        await repository.propose(
            _principal(role=Role.VIEWER),
            action="simulate_service_restart",
            target="search-api",
            reason="deploy",
        )
    denied_ticket = await repository.propose(
        _principal(),
        action="simulate_service_restart",
        target="search-api",
        reason="deploy",
    )
    denied = await repository.decide(
        denied_ticket.proposal.proposal_id,
        _principal(),
        approval_token=denied_ticket.approval_token,
        confirm=False,
    )
    assert denied.status is ApprovalStatus.DENIED
    assert denied.executed_at is None

    expired_ticket = await repository.propose(
        _principal(),
        action="simulate_service_restart",
        target="search-api",
        reason="deploy",
    )
    proposal, token_hash = repository._items[expired_ticket.proposal.proposal_id]
    repository._items[proposal.proposal_id] = (
        proposal.model_copy(update={"expires_at": datetime.now(UTC) - timedelta(seconds=1)}),
        token_hash,
    )
    with pytest.raises(OrysysError, match="expired"):
        await repository.decide(
            proposal.proposal_id,
            _principal(),
            approval_token=expired_ticket.approval_token,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_feedback_is_idempotent_trace_linked_and_reviewable() -> None:
    repository = InMemoryFeedbackRepository()
    kwargs = {
        "run_id": "run-1",
        "trace_id": "trace-1",
        "rating": 1,
        "note": "useful",
        "prompt_version": "direct-answer-v1",
        "model": "model-1",
        "corpus_version": "corpus-1",
        "route": "direct",
    }
    first = await repository.record(_principal(role=Role.VIEWER), **kwargs)
    duplicate = await repository.record(_principal(role=Role.VIEWER), **kwargs)
    with pytest.raises(AuthorizationDenied):
        await repository.mark_reviewed(first.feedback_id, _principal(role=Role.VIEWER))
    reviewed = await repository.mark_reviewed(first.feedback_id, _principal())

    assert duplicate.feedback_id == first.feedback_id
    assert first.trace_id == "trace-1"
    assert reviewed.status is FeedbackStatus.REVIEWED
    assert await repository.reviewed() == (reviewed,)
