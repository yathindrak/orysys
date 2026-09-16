from datetime import datetime
from typing import Protocol

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
