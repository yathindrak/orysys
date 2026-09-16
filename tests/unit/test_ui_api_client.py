import json

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
