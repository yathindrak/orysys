from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from orysys.application.conversations import (
    Conversation,
    ConversationMessage,
    ConversationStore,
    _with_rolling_summary,
)
from orysys.domain.errors import ResourceNotFound
from orysys.domain.identity import Principal
from orysys.domain.memory import AuditEvent, MemoryItem, MemoryKind, MemoryStatus
from orysys.memory.policy import validate_memory_content
from orysys.ports.models import MessageRole
from orysys.ports.persistence import AuditRepository, MemoryRepository


class PostgresConversationStore(ConversationStore):
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def create(self, principal: Principal) -> Conversation:
        conversation = Conversation(
            conversation_id=str(uuid4()),
            tenant_id=principal.tenant_id,
            owner_subject=principal.subject,
        )
        async with await psycopg.AsyncConnection.connect(self._dsn) as connection:
            await connection.execute(
                """INSERT INTO conversations
                   (conversation_id, tenant_id, owner_subject, created_at,
                    summary, summarized_message_count)
                   VALUES (%s, %s, %s, %s, NULL, 0)""",
                (
                    conversation.conversation_id,
                    conversation.tenant_id,
                    conversation.owner_subject,
                    conversation.created_at,
                ),
            )
        return conversation

    async def get(self, conversation_id: str, principal: Principal) -> Conversation:
        async with await psycopg.AsyncConnection.connect(
            self._dsn, row_factory=dict_row
        ) as connection:
            row = await (
                await connection.execute(
                    """SELECT conversation_id, tenant_id, owner_subject, created_at,
                              summary, summarized_message_count
                       FROM conversations
                       WHERE conversation_id = %s AND tenant_id = %s AND owner_subject = %s""",
                    (conversation_id, principal.tenant_id, principal.subject),
                )
            ).fetchone()
            if row is None:
                raise ResourceNotFound("conversation")
            message_rows = await (
                await connection.execute(
                    """SELECT role, content, created_at FROM conversation_messages
                       WHERE conversation_id = %s ORDER BY message_id""",
                    (conversation_id,),
                )
            ).fetchall()
        return _conversation(row, message_rows)

    async def append(
        self,
        conversation_id: str,
        principal: Principal,
        message: ConversationMessage,
    ) -> Conversation:
        conversation = await self.get(conversation_id, principal)
        updated = _with_rolling_summary(
            conversation.model_copy(update={"messages": (*conversation.messages, message)})
        )
        async with await psycopg.AsyncConnection.connect(self._dsn) as connection:
            await connection.execute(
                """INSERT INTO conversation_messages
                   (conversation_id, role, content, created_at) VALUES (%s, %s, %s, %s)""",
                (conversation_id, message.role.value, message.content, message.created_at),
            )
            await connection.execute(
                """UPDATE conversations SET summary = %s, summarized_message_count = %s
                   WHERE conversation_id = %s AND tenant_id = %s AND owner_subject = %s""",
                (
                    updated.summary,
                    updated.summarized_message_count,
                    conversation_id,
                    principal.tenant_id,
                    principal.subject,
                ),
            )
        return updated


class PostgresAuditRepository(AuditRepository):
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def record(self, event: AuditEvent) -> None:
        async with await psycopg.AsyncConnection.connect(self._dsn) as connection:
            await connection.execute(
                """INSERT INTO audit_events
                   (audit_id, tenant_id, actor_subject, action, resource_type,
                    resource_id, outcome, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    event.audit_id,
                    event.tenant_id,
                    event.actor_subject,
                    event.action,
                    event.resource_type,
                    event.resource_id,
                    event.outcome,
                    event.created_at,
                ),
            )


class PostgresMemoryRepository(MemoryRepository):
    def __init__(self, dsn: str, audit: AuditRepository | None = None) -> None:
        self._dsn = dsn
        self._audit = audit or PostgresAuditRepository(dsn)

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
        async with await psycopg.AsyncConnection.connect(self._dsn) as connection:
            await connection.execute(
                """INSERT INTO memory_items
                   (memory_id, tenant_id, owner_subject, kind, content, purpose,
                    provenance_run_id, status, created_at, expires_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    item.memory_id,
                    item.tenant_id,
                    item.owner_subject,
                    item.kind.value,
                    item.content,
                    item.purpose,
                    item.provenance_run_id,
                    item.status.value,
                    item.created_at,
                    item.expires_at,
                ),
            )
        await self._record(item, principal, "memory.proposed", "success")
        return item

    async def confirm(self, memory_id: str, principal: Principal) -> MemoryItem:
        now = datetime.now(UTC)
        async with await psycopg.AsyncConnection.connect(
            self._dsn, row_factory=dict_row
        ) as connection:
            row = await (
                await connection.execute(
                    """UPDATE memory_items SET status = 'active', confirmed_at = %s
                       WHERE memory_id = %s AND tenant_id = %s AND owner_subject = %s
                         AND status = 'proposed' AND expires_at > %s
                       RETURNING *""",
                    (now, memory_id, principal.tenant_id, principal.subject, now),
                )
            ).fetchone()
        if row is None:
            raise ResourceNotFound("memory")
        item = _memory(row)
        await self._record(item, principal, "memory.confirmed", "success")
        return item

    async def recall(self, principal: Principal, *, limit: int = 20) -> tuple[MemoryItem, ...]:
        async with await psycopg.AsyncConnection.connect(
            self._dsn, row_factory=dict_row
        ) as connection:
            rows = await (
                await connection.execute(
                    """SELECT * FROM memory_items
                       WHERE tenant_id = %s AND owner_subject = %s AND status = 'active'
                         AND expires_at > %s
                       ORDER BY confirmed_at DESC LIMIT %s""",
                    (principal.tenant_id, principal.subject, datetime.now(UTC), limit),
                )
            ).fetchall()
        return tuple(_memory(row) for row in rows)

    async def delete(self, memory_id: str, principal: Principal) -> None:
        now = datetime.now(UTC)
        async with await psycopg.AsyncConnection.connect(self._dsn) as connection:
            cursor = await connection.execute(
                """UPDATE memory_items SET status = 'deleted', deleted_at = %s
                   WHERE memory_id = %s AND tenant_id = %s AND owner_subject = %s
                     AND status <> 'deleted'""",
                (now, memory_id, principal.tenant_id, principal.subject),
            )
        if cursor.rowcount != 1:
            raise ResourceNotFound("memory")
        await self._audit.record(
            AuditEvent(
                audit_id=str(uuid4()),
                tenant_id=principal.tenant_id,
                actor_subject=principal.subject,
                action="memory.deleted",
                resource_type="memory",
                resource_id=memory_id,
                outcome="success",
            )
        )

    async def _record(
        self, item: MemoryItem, principal: Principal, action: str, outcome: str
    ) -> None:
        await self._audit.record(
            AuditEvent(
                audit_id=str(uuid4()),
                tenant_id=principal.tenant_id,
                actor_subject=principal.subject,
                action=action,
                resource_type="memory",
                resource_id=item.memory_id,
                outcome=outcome,
            )
        )


def _conversation(row: dict[str, Any], messages: list[dict[str, Any]]) -> Conversation:
    return Conversation(
        conversation_id=row["conversation_id"],
        tenant_id=row["tenant_id"],
        owner_subject=row["owner_subject"],
        created_at=row["created_at"],
        summary=row["summary"],
        summarized_message_count=row["summarized_message_count"],
        messages=tuple(
            ConversationMessage(
                role=MessageRole(message["role"]),
                content=message["content"],
                created_at=message["created_at"],
            )
            for message in messages
        ),
    )


def _memory(row: dict[str, Any]) -> MemoryItem:
    return MemoryItem(
        memory_id=row["memory_id"],
        tenant_id=row["tenant_id"],
        owner_subject=row["owner_subject"],
        kind=MemoryKind(row["kind"]),
        content=row["content"],
        purpose=row["purpose"],
        provenance_run_id=row["provenance_run_id"],
        status=MemoryStatus(row["status"]),
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        confirmed_at=row["confirmed_at"],
        deleted_at=row["deleted_at"],
    )
