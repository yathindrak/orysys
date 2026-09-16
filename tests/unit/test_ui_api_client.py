import json
from datetime import UTC, datetime

import httpx

from orysys.ui.api_client import OrysysApiClient


def test_ui_client_parses_sse_and_forwards_access_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer access-token"
        event = {
            "schema_version": "1",
            "sequence": 0,
            "request_id": "request-1",
            "run_id": "run-1",
            "thread_id": "thread-1",
            "timestamp": "2026-09-16T00:00:00Z",
            "type": "answer.delta",
            "node": "finalize",
            "public_payload": {"text": "hello"},
        }
        content = f"id: 0\nevent: answer.delta\ndata: {json.dumps(event)}\n\n"
        return httpx.Response(200, text=content, headers={"content-type": "text/event-stream"})

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(base_url="http://test", transport=transport)
    client = OrysysApiClient(
        "http://test",
        access_token="access-token",
        client=http_client,
    )

    events = list(client.stream_message("thread-1", "hello"))

    assert events[0].public_payload == {"text": "hello"}
    http_client.close()


def test_ui_client_lists_server_allowed_tools() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/tools"
        return httpx.Response(200, json={"tools": ["knowledge.search", "mcp.read"]})

    http_client = httpx.Client(base_url="http://test", transport=httpx.MockTransport(handler))
    client = OrysysApiClient("http://test", access_token="access-token", client=http_client)

    assert client.list_tools() == ("knowledge.search", "mcp.read")
    http_client.close()


def test_ui_client_handles_approval_and_feedback() -> None:
    now = datetime.now(UTC).isoformat()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/actions/proposals":
            return httpx.Response(
                201,
                json={
                    "ticket": {
                        "proposal": {
                            "proposal_id": "proposal-1",
                            "tenant_id": "tenant-1",
                            "requester_subject": "admin",
                            "action": "simulate_service_restart",
                            "target": "search-api",
                            "reason": "deploy",
                            "action_hash": "a" * 64,
                            "status": "pending",
                            "created_at": now,
                            "expires_at": now,
                            "decided_at": None,
                            "executed_at": None,
                        },
                        "approval_token": "token-value-long-enough-for-the-api",
                    }
                },
            )
        if request.url.path.endswith("/decision"):
            proposal = json.loads(request.content)["confirm"]
            return httpx.Response(
                200,
                json={
                    "proposal": {
                        "proposal_id": "proposal-1",
                        "tenant_id": "tenant-1",
                        "requester_subject": "admin",
                        "action": "simulate_service_restart",
                        "target": "search-api",
                        "reason": "deploy",
                        "action_hash": "a" * 64,
                        "status": "approved" if proposal else "denied",
                        "created_at": now,
                        "expires_at": now,
                        "decided_at": now,
                        "executed_at": now if proposal else None,
                    }
                },
            )
        return httpx.Response(
            201,
            json={
                "feedback": {
                    "feedback_id": "feedback-1",
                    "tenant_id": "tenant-1",
                    "owner_subject": "user-1",
                    "run_id": "run-1",
                    "trace_id": "run-1",
                    "rating": 1,
                    "note": None,
                    "prompt_version": "prompt-v1",
                    "model": "model-v1",
                    "corpus_version": "corpus-v1",
                    "route": "chat",
                    "status": "submitted",
                    "created_at": now,
                    "reviewed_at": None,
                }
            },
        )

    http_client = httpx.Client(base_url="http://test", transport=httpx.MockTransport(handler))
    client = OrysysApiClient("http://test", client=http_client)

    ticket = client.propose_action(target="search-api", reason="deploy")
    proposal = client.decide_action(
        ticket.proposal.proposal_id,
        approval_token=ticket.approval_token,
        confirm=True,
    )
    feedback = client.submit_feedback("run-1", 1)

    assert proposal.status.value == "approved"
    assert feedback.trace_id == "run-1"
    http_client.close()
