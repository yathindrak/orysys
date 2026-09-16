import json

import pytest

from orysys.adapters.fakes import InMemoryKnowledgeIndex, ScriptedChatModel
from orysys.adapters.telemetry import NoopTelemetry
from orysys.application.assistant import AssistantRequest
from orysys.domain.events import EventType
from orysys.domain.evidence import Evidence
from orysys.domain.identity import AccessScope, Principal, Role
from orysys.graph.builder import build_direct_graph
from orysys.graph.nodes import DirectGraphNodes
from orysys.graph.runtime import DirectAssistantRuntime
from orysys.ports.retrieval import SearchOptions, SearchResult


class FailingKnowledgeIndex:
    async def search(self, query: str, scope: AccessScope, options: SearchOptions) -> SearchResult:
        del query, scope, options
        raise RuntimeError("Pinecone unavailable")


def _evidence() -> Evidence:
    return Evidence(
        evidence_id="ev-1",
        document_id="policy-1",
        chunk_id="chunk-1",
        title="Service Policy",
        section="Recovery",
        page=2,
        excerpt="Priority incidents have a recovery target of four hours.",
        source_uri="https://example.test/policy-1",
        content_hash="hash-1",
        corpus_version="bank-demo-v1",
    )


def _answer(evidence_id: str = "ev-1") -> str:
    return json.dumps(
        {
            "claims": [
                {
                    "text": "Priority incidents have a four-hour recovery target.",
                    "evidence_ids": [evidence_id],
                }
            ],
            "summary": "The recovery target is four hours.",
            "incomplete": False,
        }
    )


def _principal() -> Principal:
    return Principal(
        subject="analyst-1",
        tenant_id="commercial-bank",
        roles=frozenset({Role.ANALYST}),
        departments=frozenset({"operations"}),
        clearance=3,
    )


def _request() -> AssistantRequest:
    return AssistantRequest(
        request_id="request-1",
        thread_id="thread-1",
        message="What is the recovery target?",
    )


def test_direct_graph_has_explicit_reviewable_nodes() -> None:
    nodes = DirectGraphNodes(
        chat_model=ScriptedChatModel(_answer()),
        knowledge_index=InMemoryKnowledgeIndex([_evidence()]),
    )

    graph = build_direct_graph(nodes, NoopTelemetry()).get_graph()

    assert set(graph.nodes) == {
        "__start__",
        "input_policy",
        "understand_and_plan",
        "retrieve",
        "enrich_with_mcp",
        "compose_answer",
        "validate_answer",
        "repair_once",
        "finalize",
        "safe_failure",
        "__end__",
    }


@pytest.mark.asyncio
async def test_direct_graph_returns_grounded_answer_and_ordered_events() -> None:
    model = ScriptedChatModel(_answer())
    runtime = DirectAssistantRuntime(
        chat_model=model,
        knowledge_index=InMemoryKnowledgeIndex([_evidence()]),
    )

    result = await runtime.run(_request(), _principal())

    assert result.answer.claims[0].evidence_ids == ("ev-1",)
    assert all(validation.passed for validation in result.validations)
    assert [event.sequence for event in result.events] == list(range(len(result.events)))
    assert result.events[0].type is EventType.RUN_STARTED
    assert result.events[-1].type is EventType.RUN_COMPLETED
    assert model.call_count == 1


@pytest.mark.asyncio
async def test_unknown_citation_gets_one_repair() -> None:
    model = ScriptedChatModel([_answer("invented-id"), _answer()])
    runtime = DirectAssistantRuntime(
        chat_model=model,
        knowledge_index=InMemoryKnowledgeIndex([_evidence()]),
    )

    result = await runtime.run(_request(), _principal())

    assert result.answer.claims[0].evidence_ids == ("ev-1",)
    assert model.call_count == 2
    assert any(not item.passed for item in result.validations)
    assert all(item.passed for item in result.validations[-3:])


@pytest.mark.asyncio
async def test_second_invalid_answer_fails_safely() -> None:
    model = ScriptedChatModel(["not json", _answer("still-invented")])
    runtime = DirectAssistantRuntime(
        chat_model=model,
        knowledge_index=InMemoryKnowledgeIndex([_evidence()]),
    )

    result = await runtime.run(_request(), _principal())

    assert result.answer.incomplete
    assert result.answer.claims == ()
    assert "supported answer" in result.answer.summary
    assert model.call_count == 2


@pytest.mark.asyncio
async def test_no_authorized_evidence_does_not_call_model() -> None:
    model = ScriptedChatModel(_answer())
    runtime = DirectAssistantRuntime(
        chat_model=model,
        knowledge_index=InMemoryKnowledgeIndex(),
    )

    result = await runtime.run(_request(), _principal())

    assert result.answer.incomplete
    assert result.evidence == ()
    assert result.validations == ()
    assert model.call_count == 0


@pytest.mark.asyncio
async def test_retrieval_failure_returns_safe_answer_and_degraded_event() -> None:
    model = ScriptedChatModel(_answer())
    runtime = DirectAssistantRuntime(
        chat_model=model,
        knowledge_index=FailingKnowledgeIndex(),
    )

    result = await runtime.run(_request(), _principal())

    assert result.answer.incomplete
    assert not result.answer.claims
    assert model.call_count == 0
    assert any(event.type is EventType.RETRIEVAL_DEGRADED for event in result.events)


@pytest.mark.asyncio
async def test_stream_exposes_application_events_not_raw_graph_parts() -> None:
    runtime = DirectAssistantRuntime(
        chat_model=ScriptedChatModel(_answer()),
        knowledge_index=InMemoryKnowledgeIndex([_evidence()]),
    )

    events = [event async for event in runtime.stream(_request(), _principal())]

    assert events
    assert [event.sequence for event in events] == list(range(len(events)))
    assert events[-1].type is EventType.RUN_COMPLETED
