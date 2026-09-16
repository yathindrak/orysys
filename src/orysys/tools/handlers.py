from collections import Counter
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from orysys.domain.errors import AuthorizationDenied
from orysys.domain.identity import Principal
from orysys.domain.policy import ANALYTICS, KNOWLEDGE_SEARCH, MCP_READ, derive_access_scope
from orysys.domain.tools import (
    IncidentAnalyticsArguments,
    KnowledgeSearchArguments,
    McpReadArguments,
    ToolResult,
)
from orysys.ports.retrieval import KnowledgeIndex, SearchOptions

ArgumentsT = TypeVar("ArgumentsT", bound=BaseModel)


class ToolHandler(Protocol[ArgumentsT]):
    name: str
    arguments_model: type[ArgumentsT]

    async def execute(self, arguments: ArgumentsT, principal: Principal) -> ToolResult: ...


class KnowledgeSearchTool:
    name = KNOWLEDGE_SEARCH
    arguments_model = KnowledgeSearchArguments

    def __init__(self, index: KnowledgeIndex) -> None:
        self._index = index

    async def execute(
        self, arguments: KnowledgeSearchArguments, principal: Principal
    ) -> ToolResult:
        scope = derive_access_scope(principal)
        _require(scope.allowed_tools, self.name)
        result = await self._index.search(
            arguments.query,
            scope,
            SearchOptions(limit=arguments.limit, candidate_count=28, alpha=0.5),
        )
        matches = [
            {
                "evidence_id": item.evidence_id,
                "title": item.title,
                "section": item.section,
                "source_uri": str(item.source_uri),
            }
            for item in result.evidence[: arguments.limit]
        ]
        return ToolResult(
            tool_name=self.name,
            output={"matches": matches, "count": len(matches)},
            degraded=result.degraded,
        )


class IncidentAnalyticsTool:
    name = ANALYTICS
    arguments_model = IncidentAnalyticsArguments

    async def execute(
        self, arguments: IncidentAnalyticsArguments, principal: Principal
    ) -> ToolResult:
        _require(derive_access_scope(principal).allowed_tools, self.name)
        records = arguments.records
        output: dict[str, object]
        if arguments.operation == "count_by_root_cause":
            output = {
                "groups": _ranked(Counter(item.root_cause for item in records), arguments.limit)
            }
        elif arguments.operation == "recurrence":
            counts = Counter(item.root_cause for item in records)
            output = {
                "recurring": [
                    {"root_cause": key, "count": count}
                    for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
                    if count > 1
                ][: arguments.limit]
            }
        elif arguments.operation == "date_range":
            dates = [item.occurred_on for item in records]
            output = {
                "start": min(dates).isoformat(),
                "end": max(dates).isoformat(),
                "days": (max(dates) - min(dates)).days + 1,
                "count": len(records),
            }
        else:
            counts = Counter(f"{item.service}:{item.severity}" for item in records)
            output = {"groups": _ranked(counts, arguments.limit)}
        return ToolResult(tool_name=self.name, output=output)


class McpReadClient(Protocol):
    async def call(self, operation: str, identifier: str) -> dict[str, object]: ...


class McpReadTool:
    name = MCP_READ
    arguments_model = McpReadArguments

    def __init__(self, client: McpReadClient) -> None:
        self._client = client

    async def execute(self, arguments: McpReadArguments, principal: Principal) -> ToolResult:
        _require(derive_access_scope(principal).allowed_tools, self.name)
        output = await self._client.call(arguments.operation, arguments.identifier)
        return ToolResult(tool_name=self.name, output=output)


def _ranked(counts: Counter[str], limit: int) -> list[dict[str, Any]]:
    return [
        {"key": key, "count": count}
        for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def _require(allowed_tools: frozenset[str], name: str) -> None:
    if name not in allowed_tools:
        raise AuthorizationDenied
