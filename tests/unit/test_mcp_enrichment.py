import json

import pytest

from orysys.adapters.fakes import InMemoryKnowledgeIndex, ScriptedChatModel
from orysys.application.assistant import AssistantRequest
from orysys.domain.events import EventType
from orysys.domain.identity import Principal, Role
from orysys.graph.runtime import DirectAssistantRuntime
from orysys.tools.mcp_enrichment import (
    MAX_MCP_LOOKUPS,
    extract_mcp_lookups,
    mcp_record_to_evidence,
)


def test_extract_matches_exact_ids_case_insensitively() -> None:
    lookups = extract_mcp_lookups("Who owns payment-api and E-100?")
    assert [(item.operation, item.identifier) for item in lookups] == [
        ("employee_directory", "E-100"),
        ("service_catalog", "payment-api"),
    ]


def test_extract_caps_and_dedupes() -> None:
    lookups = extract_mcp_lookups(
        "PAY-2025-0214 PAY-2025-0214 pay-2025-0603 E-100 E-200 payment-api settlement-worker"
    )
    assert len(lookups) == MAX_MCP_LOOKUPS


def test_extract_no_ids_returns_empty() -> None:
    assert extract_mcp_lookups("What does the Remote Access Policy require?") == ()


def test_mcp_record_converts_to_citable_evidence() -> None:
    (lookup,) = extract_mcp_lookups("incident_record PAY-2025-0214")
    evidence = mcp_record_to_evidence(
        lookup, {"found": True, "record": {"incident_id": "PAY-2025-0214"}}
    )
    assert evidence is not None
    assert evidence.evidence_id == "mcp:incident_record:PAY-2025-0214"
    assert "PAY-2025-0214" in evidence.excerpt


def test_mcp_missing_record_returns_none() -> None:
    (lookup,) = extract_mcp_lookups("E-100")
    assert mcp_record_to_evidence(lookup, {"found": False, "record": None}) is None


class _FakeMcp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def call(self, operation: str, identifier: str) -> dict[str, object]:
        self.calls.append((operation, identifier))
        return {"found": True, "record": {"id": identifier}}


def _answer() -> str:
    return json.dumps(
        {
            "claims": [
                {
                    "text": "Payment API is owned by Payments SRE.",
                    "evidence_ids": ["mcp:service_catalog:payment-api"],
                }
            ],
            "summary": "Payment API is owned by Payments SRE.",
            "incomplete": False,
        }
    )


def _request(message: str) -> AssistantRequest:
    return AssistantRequest(request_id="r-1", thread_id="t-1", message=message)


def _principal(role: Role) -> Principal:
    return Principal(
        subject=f"{role.value}-1",
        tenant_id="commercial-bank",
        roles=frozenset({role}),
        departments=frozenset({"payments"}),
        clearance=3,
    )


@pytest.mark.asyncio
async def test_analyst_enriches_with_mcp_evidence() -> None:
    mcp = _FakeMcp()
    runtime = DirectAssistantRuntime(
        chat_model=ScriptedChatModel(_answer()),
        knowledge_index=InMemoryKnowledgeIndex(),
        mcp_client=mcp,
    )
    # Seed retrieval evidence so compose runs; MCP evidence is appended.
    from orysys.domain.evidence import Evidence

    seed = Evidence(
        evidence_id="ev-1",
        document_id="doc-1",
        chunk_id="c-1",
        title="Seed",
        excerpt="Seed excerpt.",
        source_uri="https://example.test/seed",
        content_hash="h",
        corpus_version="bank-demo-v1",
    )
    runtime = DirectAssistantRuntime(
        chat_model=ScriptedChatModel(_answer()),
        knowledge_index=InMemoryKnowledgeIndex([seed]),
        mcp_client=mcp,
    )
    result = await runtime.run(_request("Who owns payment-api?"), _principal(Role.ANALYST))
    assert mcp.calls == [("service_catalog", "payment-api")]
    assert "mcp:service_catalog:payment-api" in {item.evidence_id for item in result.evidence}
    assert any(event.type is EventType.TOOL_COMPLETED for event in result.events)


@pytest.mark.asyncio
async def test_viewer_never_calls_mcp() -> None:
    mcp = _FakeMcp()
    from orysys.domain.evidence import Evidence

    seed = Evidence(
        evidence_id="ev-1",
        document_id="doc-1",
        chunk_id="c-1",
        title="Seed",
        excerpt="Seed excerpt.",
        source_uri="https://example.test/seed",
        content_hash="h",
        corpus_version="bank-demo-v1",
    )
    runtime = DirectAssistantRuntime(
        chat_model=ScriptedChatModel(
            json.dumps(
                {
                    "claims": [{"text": "Seed.", "evidence_ids": ["ev-1"]}],
                    "summary": "Seed.",
                    "incomplete": False,
                }
            )
        ),
        knowledge_index=InMemoryKnowledgeIndex([seed]),
        mcp_client=mcp,
    )
    result = await runtime.run(_request("Who owns payment-api?"), _principal(Role.VIEWER))
    assert mcp.calls == []
    assert all(not item.evidence_id.startswith("mcp:") for item in result.evidence)
    assert any(event.type is EventType.TOOL_DENIED for event in result.events)
