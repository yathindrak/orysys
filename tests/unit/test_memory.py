from datetime import UTC, datetime, timedelta

import pytest

from orysys.domain.errors import OrysysError, ResourceNotFound
from orysys.domain.identity import Principal, Role
from orysys.domain.memory import MemoryKind
from orysys.memory.in_memory import InMemoryMemoryRepository


def _principal(subject: str, tenant: str = "bank-a") -> Principal:
    return Principal(
        subject=subject,
        tenant_id=tenant,
        roles=frozenset({Role.VIEWER}),
    )


@pytest.mark.asyncio
async def test_memory_requires_confirmation_and_is_owner_scoped() -> None:
    repository = InMemoryMemoryRepository()
    owner = _principal("owner")
    item = await repository.propose(
        owner,
        kind=MemoryKind.PREFERENCE,
        content="Prefer concise incident summaries.",
        purpose="Format future answers",
        provenance_run_id="run-1",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )

    assert await repository.recall(owner) == ()
    with pytest.raises(ResourceNotFound):
        await repository.confirm(item.memory_id, _principal("other"))

    confirmed = await repository.confirm(item.memory_id, owner)
    assert await repository.recall(owner) == (confirmed,)
    assert await repository.recall(_principal("owner", "bank-b")) == ()

    await repository.delete(item.memory_id, owner)
    assert await repository.recall(owner) == ()
    assert [event.action for event in repository.audit_events] == [
        "memory.proposed",
        "memory.confirmed",
        "memory.deleted",
    ]


@pytest.mark.asyncio
async def test_memory_rejects_credentials() -> None:
    repository = InMemoryMemoryRepository()

    with pytest.raises(OrysysError) as caught:
        await repository.propose(
            _principal("owner"),
            kind=MemoryKind.FACT,
            content="The API token is do-not-save-this.",
            purpose="Future access",
            provenance_run_id="run-1",
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )

    assert caught.value.code == "memory_sensitive_content"
