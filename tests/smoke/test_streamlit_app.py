from datetime import UTC, datetime
from pathlib import Path

from pytest import MonkeyPatch
from streamlit.testing.v1 import AppTest

from orysys.application.conversations import Conversation
from orysys.ui.api_client import OrysysApiClient


def test_streamlit_chat_shell_renders_without_custom_html(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("ORYSYS_AUTH_ENABLED", "false")

    def create_conversation(client: OrysysApiClient) -> Conversation:
        del client
        return Conversation(
            conversation_id="conversation-1",
            tenant_id="commercial-bank",
            owner_subject="test-user",
            created_at=datetime.now(UTC),
        )

    monkeypatch.setattr(OrysysApiClient, "create_conversation", create_conversation)
    monkeypatch.setattr(OrysysApiClient, "list_tools", lambda self: ("admin.impactful_action",))
    path = Path(__file__).parents[2] / "src/orysys/ui/app.py"

    app = AppTest.from_file(str(path)).run(timeout=10)

    assert not app.exception
    assert [item.value for item in app.title] == ["✦ Orysys"]
    assert len(app.chat_input) == 1
    assert [item.label for item in app.button] == [
        "What caused incident PAY-2025-0214 (error PAY-DB-042)?",
        "How do I mitigate payment database saturation?",
        "What does the Remote Access Policy require?",
        "What caused the PAY-2025-0603 settlement delay?",
        "New conversation",
        "Request restart approval",
    ]
    new_conversation = next(item for item in app.button if item.label == "New conversation")
    assert new_conversation.disabled


def test_administrator_controls_hidden_without_admin_tool(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("ORYSYS_AUTH_ENABLED", "false")

    def create_conversation(client: OrysysApiClient) -> Conversation:
        del client
        return Conversation(
            conversation_id="conversation-1",
            tenant_id="commercial-bank",
            owner_subject="test-user",
            created_at=datetime.now(UTC),
        )

    monkeypatch.setattr(OrysysApiClient, "create_conversation", create_conversation)
    monkeypatch.setattr(OrysysApiClient, "list_tools", lambda self: ("knowledge.search",))
    path = Path(__file__).parents[2] / "src/orysys/ui/app.py"

    app = AppTest.from_file(str(path)).run(timeout=10)

    assert not app.exception
    assert "Request restart approval" not in [item.label for item in app.button]


def test_new_conversation_is_available_only_after_a_message(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("ORYSYS_AUTH_ENABLED", "false")
    created: list[str] = []

    def create_conversation(client: OrysysApiClient) -> Conversation:
        del client
        conversation_id = f"conversation-{len(created) + 1}"
        created.append(conversation_id)
        return Conversation(
            conversation_id=conversation_id,
            tenant_id="commercial-bank",
            owner_subject="test-user",
            created_at=datetime.now(UTC),
        )

    monkeypatch.setattr(OrysysApiClient, "create_conversation", create_conversation)
    path = Path(__file__).parents[2] / "src/orysys/ui/app.py"
    app = AppTest.from_file(str(path)).run(timeout=10)

    assert created == ["conversation-1"]
    new_conversation = next(item for item in app.button if item.label == "New conversation")
    assert new_conversation.disabled

    app.session_state["messages"] = [{"role": "user", "content": "hello"}]
    app.run(timeout=10)
    new_conversation = next(item for item in app.button if item.label == "New conversation")
    assert not new_conversation.disabled
    assert len(app.chat_message) == 1

    new_conversation.click().run(timeout=10)

    assert created == ["conversation-1", "conversation-2"]
    assert app.session_state["messages"] == []
    new_conversation = next(item for item in app.button if item.label == "New conversation")
    assert new_conversation.disabled
    assert len(app.chat_message) == 0
