import asyncio
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from orysys.domain.errors import ResourceNotFound
from orysys.domain.identity import Principal
from orysys.ports.models import MessageRole


class ConversationMessage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    role: MessageRole
    content: str = Field(min_length=1, max_length=8_000)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Conversation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    conversation_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    owner_subject: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    messages: tuple[ConversationMessage, ...] = ()
    summary: str | None = Field(default=None, max_length=2_000)
    summarized_message_count: int = Field(default=0, ge=0)


class ConversationSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    conversation_id: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    message_count: int = Field(default=0, ge=0)
    preview: str = Field(default="", max_length=200)


def _summary(conversation: Conversation) -> ConversationSummary:
    preview = ""
    if conversation.messages:
        preview = conversation.messages[-1].content.strip().replace("\n", " ")[:200]
    return ConversationSummary(
        conversation_id=conversation.conversation_id,
        created_at=conversation.created_at,
        message_count=len(conversation.messages),
        preview=preview,
    )


class ConversationStore(Protocol):
    async def create(self, principal: Principal) -> Conversation: ...

    async def get(self, conversation_id: str, principal: Principal) -> Conversation: ...

    async def list(
        self,
        principal: Principal,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[ConversationSummary, ...]: ...

    async def append(
        self,
        conversation_id: str,
        principal: Principal,
        message: ConversationMessage,
    ) -> Conversation: ...


class InMemoryConversationStore:
    """Process-local WP-05 store; durable checkpoints replace it in WP-09."""

    def __init__(self) -> None:
        self._items: dict[str, Conversation] = {}
        self._lock = asyncio.Lock()

    async def create(self, principal: Principal) -> Conversation:
        conversation = Conversation(
            conversation_id=str(uuid4()),
            tenant_id=principal.tenant_id,
            owner_subject=principal.subject,
        )
        async with self._lock:
            self._items[conversation.conversation_id] = conversation
        return conversation

    async def get(self, conversation_id: str, principal: Principal) -> Conversation:
        async with self._lock:
            conversation = self._items.get(conversation_id)
        if conversation is None or not _owned_by(conversation, principal):
            raise ResourceNotFound("conversation")
        return conversation

    async def append(
        self,
        conversation_id: str,
        principal: Principal,
        message: ConversationMessage,
    ) -> Conversation:
        async with self._lock:
            conversation = self._items.get(conversation_id)
            if conversation is None or not _owned_by(conversation, principal):
                raise ResourceNotFound("conversation")
            updated = conversation.model_copy(
                update={"messages": (*conversation.messages, message)}
            )
            updated = _with_rolling_summary(updated)
            self._items[conversation_id] = updated
            return updated

    async def list(
        self,
        principal: Principal,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[ConversationSummary, ...]:
        async with self._lock:
            owned = [item for item in self._items.values() if _owned_by(item, principal)]
        owned.sort(key=lambda item: item.created_at, reverse=True)
        return tuple(_summary(item) for item in owned[offset : offset + limit])


def conversation_context(conversation: Conversation) -> tuple[ConversationMessage, ...]:
    recent = conversation.messages[-8:]
    if conversation.summary is None:
        return recent
    summary = ConversationMessage(
        role=MessageRole.SYSTEM,
        content=f"Earlier conversation summary: {conversation.summary}",
    )
    return (summary, *recent)


def _with_rolling_summary(conversation: Conversation) -> Conversation:
    if len(conversation.messages) <= 12:
        return conversation
    summarize_to = len(conversation.messages) - 8
    older = conversation.messages[:summarize_to]
    parts = [f"{item.role.value}: {item.content.strip()}" for item in older]
    summary = " | ".join(parts)[-2_000:]
    return conversation.model_copy(
        update={"summary": summary, "summarized_message_count": summarize_to}
    )


def _owned_by(conversation: Conversation, principal: Principal) -> bool:
    return (
        conversation.tenant_id == principal.tenant_id
        and conversation.owner_subject == principal.subject
    )
