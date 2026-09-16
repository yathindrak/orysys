import json

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from orysys.adapters.fakes import InMemoryKnowledgeIndex, ScriptedChatModel
from orysys.application.assistant import AssistantRequest
from orysys.bootstrap import _checkpoint_serializer
from orysys.domain.evidence import Evidence
from orysys.domain.identity import Principal, Role
from orysys.graph.runtime import DirectAssistantRuntime, _checkpoint_config


@pytest.mark.asyncio
async def test_direct_graph_persists_run_checkpoint_for_restart_recovery() -> None:
    checkpointer = InMemorySaver(serde=_checkpoint_serializer())
    request = AssistantRequest(
        request_id="request-1", thread_id="thread-1", message="What is the target?"
    )
    principal = Principal(
        subject="analyst-1",
        tenant_id="bank-a",
        roles=frozenset({Role.ANALYST}),
        clearance=3,
    )
    evidence = Evidence(
        evidence_id="ev-1",
        document_id="policy-1",
        chunk_id="chunk-1",
        title="Policy",
        excerpt="The target is four hours.",
        source_uri="https://example.test/policy",
        content_hash="hash-1",
        corpus_version="test-v1",
    )
    answer = json.dumps(
        {
            "claims": [{"text": "The target is four hours.", "evidence_ids": ["ev-1"]}],
            "summary": "The target is four hours.",
            "incomplete": False,
        }
    )
    runtime = DirectAssistantRuntime(
        chat_model=ScriptedChatModel(answer),
        knowledge_index=InMemoryKnowledgeIndex([evidence]),
        checkpointer=checkpointer,
    )

    await runtime.run(request, principal)
    saved = await checkpointer.aget_tuple(_checkpoint_config(request, principal))

    assert saved is not None
    assert saved.checkpoint["channel_values"]["final_answer"].summary == (
        "The target is four hours."
    )
