import json

from fastapi.testclient import TestClient

from orysys.adapters.fakes import InMemoryKnowledgeIndex, ScriptedChatModel
from orysys.api.app import create_app
from orysys.config import Settings
from orysys.domain.evidence import Evidence
from orysys.graph.runtime import DirectAssistantRuntime


def _evidence() -> Evidence:
    return Evidence(
        evidence_id="ev-1",
        document_id="policy-1",
        chunk_id="chunk-1",
        title="Recovery Policy",
        section="Targets",
        page=2,
        excerpt="Priority incidents have a four-hour recovery target.",
        source_uri="https://example.test/policy",
        content_hash="hash-1",
        corpus_version="test-v1",
    )


def _model_answer() -> str:
    return json.dumps(
        {
            "claims": [
                {
                    "text": "The recovery target is four hours.",
                    "evidence_ids": ["ev-1"],
                }
            ],
            "summary": "The recovery target is four hours.",
            "incomplete": False,
        }
    )


def _events(response_text: str) -> list[dict[str, object]]:
    return [
        json.loads(line[6:]) for line in response_text.splitlines() if line.startswith("data: ")
    ]


def test_two_turn_conversation_streams_ordered_sse_and_persists_visible_history() -> None:
    model = ScriptedChatModel(_model_answer())
    runtime = DirectAssistantRuntime(
        chat_model=model,
        knowledge_index=InMemoryKnowledgeIndex([_evidence()]),
    )
    app = create_app(
        Settings(environment="test", use_fake_adapters=True, auth_enabled=False),
        runtime=runtime,
    )
    with TestClient(app) as client:
        created = client.post("/v1/conversations")
        conversation_id = created.json()["conversation"]["conversation_id"]

        first = client.post(
            f"/v1/conversations/{conversation_id}/messages",
            json={"message": "What is the recovery target?"},
        )
        second = client.post(
            f"/v1/conversations/{conversation_id}/messages",
            json={"message": "Please state that again."},
        )
        conversation = client.get(f"/v1/conversations/{conversation_id}")

    assert created.status_code == 201
    assert first.status_code == 200
    assert first.headers["content-type"].startswith("text/event-stream")
    assert second.status_code == 200
    first_events = _events(first.text)
    assert [event["sequence"] for event in first_events] == list(range(len(first_events)))
    assert first_events[-1]["type"] == "run.completed"
    assert any(event["type"] == "answer.completed" for event in first_events)
    assert "secret-token" not in first.text
    messages = conversation.json()["messages"]
    assert [message["role"] for message in messages] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    second_prompt = model.requests[1].messages[-1].content
    assert "What is the recovery target?" in second_prompt
    assert "The recovery target is four hours." in second_prompt


def test_unknown_conversation_uses_stable_public_error() -> None:
    app = create_app(Settings(environment="test", use_fake_adapters=True, auth_enabled=False))

    with TestClient(app) as client:
        response = client.get("/v1/conversations/not-found")

    assert response.status_code == 404
    assert response.json() == {
        "code": "resource_not_found",
        "message": "The requested conversation was not found.",
        "retryable": False,
    }


def test_list_conversations_returns_metadata_without_messages() -> None:
    model = ScriptedChatModel(_model_answer())
    runtime = DirectAssistantRuntime(
        chat_model=model,
        knowledge_index=InMemoryKnowledgeIndex([_evidence()]),
    )
    app = create_app(
        Settings(environment="test", use_fake_adapters=True, auth_enabled=False),
        runtime=runtime,
    )
    with TestClient(app) as client:
        first = client.post("/v1/conversations").json()["conversation"]["conversation_id"]
        second = client.post("/v1/conversations").json()["conversation"]["conversation_id"]
        client.post(f"/v1/conversations/{first}/messages", json={"message": "First?"})
        listed = client.get("/v1/conversations")
        paged = client.get("/v1/conversations", params={"limit": 1, "offset": 1})
        invalid = client.get("/v1/conversations", params={"limit": 0})

    assert listed.status_code == 200
    items = listed.json()["conversations"]
    assert [item["conversation_id"] for item in items] == [second, first]
    assert all("messages" not in item for item in items)
    first_item = next(item for item in items if item["conversation_id"] == first)
    assert first_item["message_count"] == 2
    assert first_item["preview"] != ""
    assert [item["conversation_id"] for item in paged.json()["conversations"]] == [first]
    assert invalid.status_code == 422
