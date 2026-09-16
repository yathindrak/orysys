from collections.abc import Awaitable, Callable
from typing import Any, cast

from langgraph.graph import END, START, StateGraph

from orysys.graph.nodes import DirectGraphNodes, route_after_compose, route_after_validation
from orysys.graph.state import AssistantState
from orysys.ports.services import Telemetry


def build_direct_graph(
    nodes: DirectGraphNodes,
    telemetry: Telemetry,
    *,
    checkpointer: Any | None = None,
) -> Any:
    builder = StateGraph(AssistantState)
    builder.add_node("input_policy", _traced("input_policy", nodes.input_policy, telemetry))
    builder.add_node(
        "understand_and_plan",
        _traced("understand_and_plan", nodes.understand_and_plan, telemetry),
    )
    builder.add_node("retrieve", _traced("retrieve", nodes.retrieve, telemetry))
    builder.add_node("compose_answer", _traced("compose_answer", nodes.compose_answer, telemetry))
    builder.add_node(
        "validate_answer", _traced("validate_answer", nodes.validate_answer, telemetry)
    )
    builder.add_node("repair_once", _traced("repair_once", nodes.repair_once, telemetry))
    builder.add_node("finalize", _traced("finalize", nodes.finalize, telemetry))
    builder.add_node("safe_failure", _traced("safe_failure", nodes.safe_failure, telemetry))
    builder.add_edge(START, "input_policy")
    builder.add_edge("input_policy", "understand_and_plan")
    builder.add_edge("understand_and_plan", "retrieve")
    builder.add_edge("retrieve", "compose_answer")
    builder.add_conditional_edges(
        "compose_answer",
        route_after_compose,
        {"validate_answer": "validate_answer", "safe_failure": "safe_failure"},
    )
    builder.add_conditional_edges(
        "validate_answer",
        route_after_validation,
        {
            "finalize": "finalize",
            "repair_once": "repair_once",
            "safe_failure": "safe_failure",
        },
    )
    builder.add_edge("repair_once", "validate_answer")
    builder.add_edge("finalize", END)
    builder.add_edge("safe_failure", END)
    return cast(Any, builder.compile(checkpointer=checkpointer))


def _traced(
    name: str,
    node: Callable[[AssistantState], Awaitable[AssistantState]],
    telemetry: Telemetry,
) -> Any:
    async def wrapped(state: AssistantState) -> AssistantState:
        request = state["request"]
        attributes: dict[str, object] = {
            "node": name,
            "request_id": request.request_id,
            "run_id": state["run_id"],
            "thread_id": request.thread_id,
            "route": state.get("route", "pending"),
        }
        async with telemetry.span(f"orysys.graph.{name}", attributes):
            return await node(state)

    return cast(Any, wrapped)
