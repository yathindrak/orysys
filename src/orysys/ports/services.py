from contextlib import AbstractAsyncContextManager
from typing import Protocol

from orysys.domain.events import ActivityEvent
from orysys.domain.identity import Principal
from orysys.domain.tools import ToolRequest, ToolResult, ToolRunContext


class IdentityVerifier(Protocol):
    async def verify(self, token: str) -> Principal: ...


class LimitDecision(Protocol):
    allowed: bool
    retry_after_seconds: int | None


class RateLimiter(Protocol):
    async def consume(self, subject: str, cost: int = 1) -> LimitDecision: ...


class ToolGateway(Protocol):
    def available(self, principal: Principal) -> tuple[str, ...]: ...

    async def execute(
        self,
        request: ToolRequest,
        principal: Principal,
        context: ToolRunContext,
    ) -> ToolResult: ...


class Telemetry(Protocol):
    def span(
        self, name: str, attributes: dict[str, object] | None = None
    ) -> AbstractAsyncContextManager[None]: ...

    async def event(self, event: ActivityEvent) -> None: ...
