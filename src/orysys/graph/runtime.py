from collections.abc import AsyncIterator
from hashlib import sha256
from typing import Any, cast
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict

from orysys.adapters.telemetry import NoopTelemetry
from orysys.application.assistant import AssistantRequest
from orysys.domain.events import ActivityEvent
from orysys.domain.evidence import Evidence, GroundedAnswer
from orysys.domain.identity import Principal
from orysys.domain.validation import ValidationResult
from orysys.graph.builder import build_direct_graph
from orysys.graph.nodes import DirectGraphNodes
from orysys.graph.state import AssistantState
from orysys.ports.models import ChatModel
from orysys.ports.retrieval import KnowledgeIndex, SearchOptions
from orysys.ports.services import Telemetry


class AssistantRunResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    answer: GroundedAnswer
    evidence: tuple[Evidence, ...]
    validations: tuple[ValidationResult, ...]
    events: tuple[ActivityEvent, ...]


class DirectAssistantRuntime:
    def __init__(
        self,
        *,
        chat_model: ChatModel,
        knowledge_index: KnowledgeIndex,
        search_options: SearchOptions | None = None,
        telemetry: Telemetry | None = None,
        checkpointer: Any | None = None,
        mcp_client: Any | None = None,
    ) -> None:
        nodes = DirectGraphNodes(
            chat_model=chat_model,
            knowledge_index=knowledge_index,
            search_options=search_options,
            mcp_client=mcp_client,
        )
        self._telemetry = telemetry or NoopTelemetry()
        self._graph = build_direct_graph(nodes, self._telemetry, checkpointer=checkpointer)

    async def run(self, request: AssistantRequest, principal: Principal) -> AssistantRunResult:
        run_id = str(uuid4())
        initial: AssistantState = {
            "request": request,
            "principal": principal,
            "run_id": run_id,
            "validations": [],
            "events": [],
        }
        attributes = self._run_attributes(request, principal, run_id)
        async with self._telemetry.span("orysys.assistant", attributes):
            raw: dict[str, Any] = await self._graph.ainvoke(
                initial, _checkpoint_config(request, principal)
            )
        state = cast(AssistantState, raw)
        return AssistantRunResult(
            run_id=run_id,
            answer=state["final_answer"],
            evidence=state.get("evidence", ()),
            validations=tuple(state.get("validations", [])),
            events=tuple(state.get("events", [])),
        )

    async def stream(
        self, request: AssistantRequest, principal: Principal
    ) -> AsyncIterator[ActivityEvent]:
        run_id = str(uuid4())
        initial: AssistantState = {
            "request": request,
            "principal": principal,
            "run_id": run_id,
            "validations": [],
            "events": [],
        }
        attributes = self._run_attributes(request, principal, run_id)
        async with self._telemetry.span("orysys.assistant", attributes):
            async for part in self._graph.astream(
                initial,
                _checkpoint_config(request, principal),
                stream_mode="updates",
                version="v2",
            ):
                if part["type"] != "updates":
                    continue
                for update in part["data"].values():
                    if isinstance(update, dict):
                        for event in update.get("events", []):
                            parsed = ActivityEvent.model_validate(event)
                            await self._telemetry.event(parsed)
                            yield parsed

    @staticmethod
    def _run_attributes(
        request: AssistantRequest, principal: Principal, run_id: str
    ) -> dict[str, object]:
        return {
            "request_id": request.request_id,
            "run_id": run_id,
            "thread_id": request.thread_id,
            "tenant_id": principal.tenant_id,
            "roles": sorted(role.value for role in principal.roles),
        }


def _checkpoint_config(request: AssistantRequest, principal: Principal) -> RunnableConfig:
    thread_key = sha256(
        (
            f"{principal.tenant_id}\0{principal.subject}\0{request.thread_id}\0{request.request_id}"
        ).encode()
    ).hexdigest()
    return {"configurable": {"thread_id": thread_key}}
