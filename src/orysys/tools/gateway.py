import asyncio
import json
from typing import Any

from pydantic import ValidationError

from orysys.adapters.telemetry import NoopTelemetry
from orysys.domain.errors import AuthorizationDenied, OrysysError, ProviderUnavailable
from orysys.domain.events import ActivityEvent, EventType
from orysys.domain.identity import Principal
from orysys.domain.policy import derive_access_scope
from orysys.domain.tools import ToolRequest, ToolResult, ToolRunContext
from orysys.ports.services import Telemetry
from orysys.tools.handlers import ToolHandler


class AuthorizedToolGateway:
    def __init__(
        self,
        handlers: list[ToolHandler[Any]],
        *,
        telemetry: Telemetry | None = None,
        timeout_seconds: float = 8.0,
        max_output_bytes: int = 16_384,
    ) -> None:
        self._handlers = {handler.name: handler for handler in handlers}
        self._telemetry = telemetry or NoopTelemetry()
        self._timeout = timeout_seconds
        self._max_output_bytes = max_output_bytes
        self._results: dict[tuple[str, str, str, str], ToolResult] = {}
        self._lock = asyncio.Lock()

    def available(self, principal: Principal) -> tuple[str, ...]:
        allowed = derive_access_scope(principal).allowed_tools
        return tuple(sorted(name for name in self._handlers if name in allowed))

    async def execute(
        self,
        request: ToolRequest,
        principal: Principal,
        context: ToolRunContext,
    ) -> ToolResult:
        requested = _event(context, EventType.TOOL_REQUESTED, request.tool_name)
        await self._telemetry.event(requested)
        handler = self._handlers.get(request.tool_name)
        if handler is None or request.tool_name not in derive_access_scope(principal).allowed_tools:
            await self._telemetry.event(
                _event(context, EventType.TOOL_DENIED, request.tool_name, sequence_offset=1)
            )
            raise AuthorizationDenied

        key = (
            principal.tenant_id,
            principal.subject,
            request.tool_name,
            request.idempotency_key,
        )
        async with self._lock:
            cached = self._results.get(key)
        if cached is not None:
            await self._telemetry.event(
                _event(context, EventType.TOOL_COMPLETED, request.tool_name, sequence_offset=1)
            )
            return cached
        try:
            arguments = handler.arguments_model.model_validate(request.arguments)
            async with asyncio.timeout(self._timeout):
                result = await handler.execute(arguments, principal)
        except ValidationError as error:
            await self._telemetry.event(
                _event(context, EventType.TOOL_DENIED, request.tool_name, sequence_offset=1)
            )
            raise OrysysError(
                "invalid_tool_arguments", "The tool arguments are invalid."
            ) from error
        except TimeoutError as error:
            await self._telemetry.event(
                _event(context, EventType.TOOL_FAILED, request.tool_name, sequence_offset=1)
            )
            raise ProviderUnavailable("tool") from error
        except AuthorizationDenied:
            await self._telemetry.event(
                _event(context, EventType.TOOL_DENIED, request.tool_name, sequence_offset=1)
            )
            raise
        except OrysysError:
            await self._telemetry.event(
                _event(context, EventType.TOOL_FAILED, request.tool_name, sequence_offset=1)
            )
            raise
        except Exception as error:
            await self._telemetry.event(
                _event(context, EventType.TOOL_FAILED, request.tool_name, sequence_offset=1)
            )
            raise ProviderUnavailable("tool") from error
        payload = json.dumps(result.output, default=str, separators=(",", ":")).encode()
        if len(payload) > self._max_output_bytes:
            await self._telemetry.event(
                _event(context, EventType.TOOL_FAILED, request.tool_name, sequence_offset=1)
            )
            raise OrysysError("tool_output_too_large", "The tool response exceeded its safe limit.")
        async with self._lock:
            self._results[key] = result
        await self._telemetry.event(
            _event(context, EventType.TOOL_COMPLETED, request.tool_name, sequence_offset=1)
        )
        return result


def _event(
    context: ToolRunContext,
    event_type: EventType,
    tool_name: str,
    *,
    sequence_offset: int = 0,
) -> ActivityEvent:
    return ActivityEvent(
        sequence=context.sequence + sequence_offset,
        request_id=context.request_id,
        run_id=context.run_id,
        thread_id=context.thread_id,
        type=event_type,
        node="tool_gateway",
        public_payload={"tool": tool_name},
    )
