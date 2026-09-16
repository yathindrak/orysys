import pytest

from orysys.application.conversations import ConversationMessage, InMemoryConversationStore
from orysys.domain.errors import ResourceNotFound
from orysys.domain.identity import Principal, Role
from orysys.ports.models import MessageRole


def _principal(subject: str, tenant: str = "tenant-1") -> Principal:
    return Principal(
        subject=subject,
        tenant_id=tenant,
        roles=frozenset({Role.VIEWER}),
    )


@pytest.mark.asyncio
async def test_conversation_store_enforces_owner_and_tenant() -> None:
    store = InMemoryConversationStore()
    owner = _principal("owner")
    conversation = await store.create(owner)
    await store.append(
        conversation.conversation_id,
        owner,
        ConversationMessage(role=MessageRole.USER, content="Hello"),
    )

    saved = await store.get(conversation.conversation_id, owner)

    assert saved.messages[0].content == "Hello"
    with pytest.raises(ResourceNotFound):
        await store.get(conversation.conversation_id, _principal("other"))
    with pytest.raises(ResourceNotFound):
        await store.get(conversation.conversation_id, _principal("owner", "tenant-2"))
