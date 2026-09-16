import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from orysys.domain.errors import ResourceNotFound
from orysys.domain.identity import Principal
from orysys.domain.memory import AuditEvent, MemoryItem, MemoryKind, MemoryStatus
from orysys.memory.policy import validate_memory_content


class InMemoryMemoryRepository:
    def __init__(self) -> None:
        self._items: dict[str, MemoryItem] = {}
        self.audit_events: list[AuditEvent] = []
        self._lock = asyncio.Lock()

    async def propose(
        self,
        principal: Principal,
        *,
        kind: MemoryKind,
        content: str,
        purpose: str,
        provenance_run_id: str,
        expires_at: datetime,
    ) -> MemoryItem:
        validate_memory_content(f"{content}\n{purpose}", expires_at)
        item = MemoryItem(
            memory_id=str(uuid4()),
            tenant_id=principal.tenant_id,
            owner_subject=principal.subject,
            kind=kind,
            content=content,
            purpose=purpose,
            provenance_run_id=provenance_run_id,
            expires_at=expires_at,
        )
        async with self._lock:
            self._items[item.memory_id] = item
            self._audit(item, principal, "memory.proposed")
        return item

    async def confirm(self, memory_id: str, principal: Principal) -> MemoryItem:
        async with self._lock:
            item = self._owned(memory_id, principal)
            if item.status is not MemoryStatus.PROPOSED or item.expires_at <= datetime.now(UTC):
                raise ResourceNotFound("memory")
            item = item.model_copy(
                update={"status": MemoryStatus.ACTIVE, "confirmed_at": datetime.now(UTC)}
            )
            self._items[memory_id] = item
            self._audit(item, principal, "memory.confirmed")
            return item

    async def recall(self, principal: Principal, *, limit: int = 20) -> tuple[MemoryItem, ...]:
        now = datetime.now(UTC)
        async with self._lock:
            items = [
                item
                for item in self._items.values()
                if item.tenant_id == principal.tenant_id
                and item.owner_subject == principal.subject
                and item.status is MemoryStatus.ACTIVE
                and item.expires_at > now
            ]
        return tuple(
            sorted(items, key=lambda item: item.confirmed_at or item.created_at, reverse=True)[
                :limit
            ]
        )

    async def delete(self, memory_id: str, principal: Principal) -> None:
        async with self._lock:
            item = self._owned(memory_id, principal)
            item = item.model_copy(
                update={"status": MemoryStatus.DELETED, "deleted_at": datetime.now(UTC)}
            )
            self._items[memory_id] = item
            self._audit(item, principal, "memory.deleted")

    def _owned(self, memory_id: str, principal: Principal) -> MemoryItem:
        item = self._items.get(memory_id)
        if (
            item is None
            or item.tenant_id != principal.tenant_id
            or item.owner_subject != principal.subject
        ):
            raise ResourceNotFound("memory")
        return item

    def _audit(self, item: MemoryItem, principal: Principal, action: str) -> None:
        self.audit_events.append(
            AuditEvent(
                audit_id=str(uuid4()),
                tenant_id=principal.tenant_id,
                actor_subject=principal.subject,
                action=action,
                resource_type="memory",
                resource_id=item.memory_id,
                outcome="success",
            )
        )
