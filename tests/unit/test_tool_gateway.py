import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date

import pytest

from orysys.domain.errors import AuthorizationDenied, ProviderUnavailable
from orysys.domain.events import ActivityEvent, EventType
from orysys.domain.identity import Principal, Role
from orysys.domain.policy import ANALYTICS
from orysys.domain.tools import (
    IncidentAnalyticsArguments,
    ToolRequest,
    ToolResult,
    ToolRunContext,
)
from orysys.tools.gateway import AuthorizedToolGateway
from orysys.tools.handlers import IncidentAnalyticsTool


class RecordingTelemetry:
    def __init__(self) -> None:
        self.events: list[ActivityEvent] = []

    @asynccontextmanager
    async def span(
        self, name: str, attributes: dict[str, object] | None = None
    ) -> AsyncIterator[None]:
        del name, attributes
        yield

    async def event(self, event: ActivityEvent) -> None:
        self.events.append(event)


class SlowAnalyticsTool:
    name = ANALYTICS
    arguments_model = IncidentAnalyticsArguments

    async def execute(
        self, arguments: IncidentAnalyticsArguments, principal: Principal
    ) -> ToolResult:
        del arguments, principal
        await asyncio.sleep(0.05)
        return ToolResult(tool_name=self.name)


def _principal(role: Role) -> Principal:
    return Principal(
        subject=f"{role.value}-1",
        tenant_id="bank-a",
        roles=frozenset({role}),
        clearance=3,
    )


def _context() -> ToolRunContext:
    return ToolRunContext(
        request_id="request-1",
        run_id="run-1",
        thread_id="thread-1",
    )


def _request() -> ToolRequest:
    return ToolRequest(
        tool_name=ANALYTICS,
        idempotency_key="operation-1",
        arguments={
            "operation": "recurrence",
            "records": [
                {
                    "incident_id": "INC-1",
                    "occurred_on": date(2025, 1, 1),
                    "service": "payments",
                    "severity": "high",
                    "root_cause": "connection saturation",
                },
                {
                    "incident_id": "INC-2",
                    "occurred_on": date(2025, 2, 1),
                    "service": "payments",
                    "severity": "critical",
                    "root_cause": "connection saturation",
                },
            ],
        },
    )


@pytest.mark.asyncio
async def test_analyst_executes_bounded_analytics_idempotently() -> None:
    telemetry = RecordingTelemetry()
    gateway = AuthorizedToolGateway([IncidentAnalyticsTool()], telemetry=telemetry)

    first = await gateway.execute(_request(), _principal(Role.ANALYST), _context())
    second = await gateway.execute(_request(), _principal(Role.ANALYST), _context())

    assert first == second
    assert first.output["recurring"] == [{"root_cause": "connection saturation", "count": 2}]
    assert [event.type for event in telemetry.events] == [
        EventType.TOOL_REQUESTED,
        EventType.TOOL_COMPLETED,
        EventType.TOOL_REQUESTED,
        EventType.TOOL_COMPLETED,
    ]


@pytest.mark.asyncio
async def test_viewer_is_denied_before_analytics_handler_runs() -> None:
    telemetry = RecordingTelemetry()
    gateway = AuthorizedToolGateway([IncidentAnalyticsTool()], telemetry=telemetry)

    with pytest.raises(AuthorizationDenied):
        await gateway.execute(_request(), _principal(Role.VIEWER), _context())

    assert [event.type for event in telemetry.events] == [
        EventType.TOOL_REQUESTED,
        EventType.TOOL_DENIED,
    ]


@pytest.mark.asyncio
async def test_tool_timeout_is_safe_and_visible() -> None:
    telemetry = RecordingTelemetry()
    gateway = AuthorizedToolGateway(
        [SlowAnalyticsTool()], telemetry=telemetry, timeout_seconds=0.001
    )

    with pytest.raises(ProviderUnavailable):
        await gateway.execute(_request(), _principal(Role.ANALYST), _context())

    assert [event.type for event in telemetry.events] == [
        EventType.TOOL_REQUESTED,
        EventType.TOOL_FAILED,
    ]
