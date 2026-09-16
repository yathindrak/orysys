from typing import Any, TypedDict, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt


class ApprovalState(TypedDict, total=False):
    proposal_id: str
    decision: dict[str, object]


def build_approval_graph(checkpointer: BaseCheckpointSaver[Any]) -> Any:
    async def await_decision(state: ApprovalState) -> ApprovalState:
        decision = interrupt({"proposal_id": state["proposal_id"], "requires_confirmation": True})
        return {"decision": cast(dict[str, object], decision)}

    builder = StateGraph(ApprovalState)
    builder.add_node("await_approval", await_decision)
    builder.add_edge(START, "await_approval")
    builder.add_edge("await_approval", END)
    return builder.compile(checkpointer=checkpointer)
