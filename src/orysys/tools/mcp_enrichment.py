import hashlib
import json
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from orysys.domain.evidence import Evidence


class McpLookup(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    operation: str
    identifier: str


class McpDirectoryCaller(Protocol):
    async def call(self, operation: str, identifier: str) -> dict[str, object]: ...


MAX_MCP_LOOKUPS = 3

_KNOWN_IDS: tuple[McpLookup, ...] = (
    McpLookup(operation="employee_directory", identifier="E-100"),
    McpLookup(operation="employee_directory", identifier="E-200"),
    McpLookup(operation="service_catalog", identifier="payment-api"),
    McpLookup(operation="service_catalog", identifier="settlement-worker"),
    McpLookup(operation="incident_record", identifier="PAY-2025-0214"),
    McpLookup(operation="incident_record", identifier="PAY-2025-0603"),
)


def extract_mcp_lookups(message: str, *, max_calls: int = MAX_MCP_LOOKUPS) -> tuple[McpLookup, ...]:
    """Deterministically match exact directory IDs in a user message.

    Substring match on upper-cased text keeps behavior reviewable: no model
    decision, no regex backtracking, stable canonical order, hard cap.
    """

    normalized = message.upper()
    matched = tuple(item for item in _KNOWN_IDS if item.identifier.upper() in normalized)
    return matched[:max_calls]


def mcp_record_to_evidence(lookup: McpLookup, record: dict[str, object]) -> Evidence | None:
    """Convert one MCP directory record into citable evidence.

    Returns None when the directory reports no record so the graph simply
    continues with retrieval evidence instead of failing the run.
    """

    if not record.get("found"):
        return None
    payload = record.get("record")
    if not isinstance(payload, dict) or not payload:
        return None
    excerpt = json.dumps(payload, ensure_ascii=False, sort_keys=True)[:800]
    if not excerpt:
        return None
    evidence_id = f"mcp:{lookup.operation}:{lookup.identifier}"
    return Evidence(
        evidence_id=evidence_id,
        document_id=f"mcp-{lookup.operation}",
        chunk_id=lookup.identifier,
        title=f"{lookup.operation} {lookup.identifier}",
        section=lookup.operation,
        page=None,
        excerpt=excerpt,
        source_uri=f"orysys://mcp/{lookup.operation}/{lookup.identifier}",
        content_hash=hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
        corpus_version="mcp-directory-v1",
    )
