from datetime import UTC, datetime
from pathlib import Path

from pytest import MonkeyPatch
from streamlit.testing.v1 import AppTest

from orysys.application.conversations import Conversation
from orysys.ui.api_client import OrysysApiClient


def test_streamlit_chat_shell_renders_without_custom_html(monkeypatch: MonkeyPatch) -> None:
    def create_conversation(client: OrysysApiClient) -> Conversation:
        del client
        return Conversation(
            conversation_id="conversation-1",
            tenant_id="commercial-bank",
            owner_subject="test-user",
            created_at=datetime.now(UTC),
        )

    monkeypatch.setattr(OrysysApiClient, "create_conversation", create_conversation)
    path = Path(__file__).parents[2] / "src/orysys/ui/app.py"

    app = AppTest.from_file(str(path)).run(timeout=10)

    assert not app.exception
    assert [item.value for item in app.title] == ["✦ Orysys"]
    assert len(app.chat_input) == 1
    assert [item.label for item in app.button] == ["New conversation"]
