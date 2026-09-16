from collections.abc import AsyncIterator

import pytest
from starlette.requests import Request

from orysys.api.app import _stream_run
from orysys.application.assistant import AssistantRequest
from orysys.application.conversations import InMemoryConversationStore
from orysys.domain.errors import ProviderUnavailable
from orysys.domain.events import ActivityEvent, EventType
from orysys.domain.identity import Principal, Role


class ClosingRuntime:
    def __init__(self) -> None:
        self.closed = False

    async def stream(
        self, request: AssistantRequest, principal: Principal
    ) -> AsyncIterator[ActivityEvent]:
        del principal
        try:
            yield ActivityEvent(
                sequence=0,
                request_id=request.request_id,
                run_id="run-1",
                thread_id=request.thread_id,
                type=EventType.RUN_STARTED,
            )
        finally:
            self.closed = True


class FailingRuntime:
    async def stream(
        self, request: AssistantRequest, principal: Principal
    ) -> AsyncIterator[ActivityEvent]:
        del request, principal
        if False:
            yield
        raise ProviderUnavailable("test provider")


@pytest.mark.asyncio
async def test_disconnected_sse_client_closes_graph_stream() -> None:
    async def receive() -> dict[str, str]:
        return {"type": "http.disconnect"}

    request = Request({"type": "http", "method": "POST", "path": "/"}, receive)
    principal = Principal(
        subject="user-1",
        tenant_id="tenant-1",
        roles=frozenset({Role.VIEWER}),
    )
    assistant_request = AssistantRequest(
        request_id="request-1",
        thread_id="thread-1",
        message="hello",
    )
    runtime = ClosingRuntime()

    frames = [
        frame
        async for frame in _stream_run(
            request=request,
            assistant_request=assistant_request,
            runtime=runtime,
            store=InMemoryConversationStore(),
            principal=principal,
        )
    ]

    assert frames == []
    assert runtime.closed


@pytest.mark.asyncio
async def test_provider_failure_emits_redacted_run_failed_event() -> None:
    async def receive() -> dict[str, str]:
        return {"type": "http.request"}

    request = Request({"type": "http", "method": "POST", "path": "/"}, receive)
    principal = Principal(
        subject="user-1",
        tenant_id="tenant-1",
        roles=frozenset({Role.VIEWER}),
    )
    assistant_request = AssistantRequest(
        request_id="request-1",
        thread_id="thread-1",
        message="hello",
    )

    frames = [
        frame
        async for frame in _stream_run(
            request=request,
            assistant_request=assistant_request,
            runtime=FailingRuntime(),
            store=InMemoryConversationStore(),
            principal=principal,
        )
    ]

    payload = b"".join(frames)
    assert b"run.failed" in payload
    assert b"test provider" not in payload
