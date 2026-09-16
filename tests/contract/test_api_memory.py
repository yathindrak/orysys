from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from orysys.api.app import create_app
from orysys.application.assistant import AssistantRequest
from orysys.config import Settings
from orysys.domain.events import ActivityEvent, EventType
from orysys.domain.identity import Principal, Role
from orysys.memory.in_memory import InMemoryMemoryRepository


class CapturingRuntime:
    def __init__(self) -> None:
        self.requests: list[AssistantRequest] = []

    async def stream(
        self, request: AssistantRequest, principal: Principal
    ) -> AsyncIterator[ActivityEvent]:
        del principal
        self.requests.append(request)
        yield ActivityEvent(
            sequence=0,
            request_id=request.request_id,
            run_id="run-captured",
            thread_id=request.thread_id,
            type=EventType.RUN_COMPLETED,
        )


def test_memory_api_requires_explicit_confirmation() -> None:
    principal = Principal(
        subject="viewer-1",
        tenant_id="bank-a",
        roles=frozenset({Role.VIEWER}),
    )
    app = create_app(
        Settings(environment="test", use_fake_adapters=True, auth_enabled=False),
        principal=principal,
    )
    proposal = {
        "kind": "preference",
        "content": "Prefer concise answers.",
        "purpose": "Format future responses",
        "provenance_run_id": "run-1",
        "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
    }

    with TestClient(app) as client:
        created = client.post("/v1/memories/proposals", json=proposal)
        memory_id = created.json()["memory"]["memory_id"]
        before = client.get("/v1/memories")
        confirmed = client.post(f"/v1/memories/{memory_id}/confirm")
        after = client.get("/v1/memories")
        deleted = client.delete(f"/v1/memories/{memory_id}")

    assert created.status_code == 201
    assert before.json() == {"memories": []}
    assert confirmed.json()["memory"]["status"] == "active"
    assert [item["memory_id"] for item in after.json()["memories"]] == [memory_id]
    assert deleted.status_code == 204


def test_confirmed_memory_is_recalled_across_conversations_as_untrusted_context() -> None:
    principal = Principal(
        subject="viewer-1",
        tenant_id="bank-a",
        roles=frozenset({Role.VIEWER}),
    )
    repository = InMemoryMemoryRepository()
    runtime = CapturingRuntime()
    app = create_app(
        Settings(environment="test", use_fake_adapters=True, auth_enabled=False),
        principal=principal,
        memories=repository,
        runtime=runtime,
    )
    proposal = {
        "kind": "preference",
        "content": "Prefer concise answers.",
        "purpose": "Format future responses",
        "provenance_run_id": "run-1",
        "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
    }

    with TestClient(app) as client:
        memory_id = client.post("/v1/memories/proposals", json=proposal).json()["memory"][
            "memory_id"
        ]
        client.post(f"/v1/memories/{memory_id}/confirm")
        conversation_id = client.post("/v1/conversations").json()["conversation"]["conversation_id"]
        response = client.post(
            f"/v1/conversations/{conversation_id}/messages",
            json={"message": "Summarize the incident."},
        )

    assert response.status_code == 200
    assert runtime.requests[0].history[0].role.value == "system"
    assert "Prefer concise answers." in runtime.requests[0].history[0].content
    assert "untrusted context" in runtime.requests[0].history[0].content
