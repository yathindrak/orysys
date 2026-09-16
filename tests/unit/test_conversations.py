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


@pytest.mark.asyncio
async def test_conversation_list_is_owner_scoped_with_preview_and_pagination() -> None:
    store = InMemoryConversationStore()
    owner = _principal("owner")
    first = await store.create(owner)
    second = await store.create(owner)
    await store.append(
        first.conversation_id,
        owner,
        ConversationMessage(role=MessageRole.USER, content="First question"),
    )
    await store.append(
        second.conversation_id,
        owner,
        ConversationMessage(role=MessageRole.USER, content="Second question"),
    )

    all_items = await store.list(owner)
    assert [item.conversation_id for item in all_items] == [
        second.conversation_id,
        first.conversation_id,
    ]
    assert all_items[0].preview == "Second question"
    assert all_items[0].message_count == 1

    page = await store.list(owner, limit=1, offset=1)
    assert [item.conversation_id for item in page] == [first.conversation_id]

    assert await store.list(_principal("other")) == ()
    assert await store.list(_principal("owner", "tenant-2")) == ()
