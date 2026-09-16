import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from orysys.controls.workflow import build_approval_graph


@pytest.mark.asyncio
async def test_approval_graph_interrupts_and_resumes() -> None:
    graph = build_approval_graph(InMemorySaver())
    config = {"configurable": {"thread_id": "approval-1"}}

    interrupted = await graph.ainvoke({"proposal_id": "proposal-1"}, config)
    resumed = await graph.ainvoke(Command(resume={"confirm": True}), config)

    assert interrupted["__interrupt__"][0].value["proposal_id"] == "proposal-1"
    assert resumed["decision"] == {"confirm": True}
