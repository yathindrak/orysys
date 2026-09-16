from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_name: str = Field(min_length=1)
    arguments: dict[str, object] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1)


class ToolResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_name: str
    output: dict[str, object] = Field(default_factory=dict)
    degraded: bool = False


class ToolRunContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    sequence: int = Field(default=0, ge=0)


class KnowledgeSearchArguments(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    query: str = Field(min_length=1, max_length=1_000)
    limit: int = Field(default=5, ge=1, le=12)


class IncidentRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    incident_id: str = Field(min_length=1, max_length=100)
    occurred_on: date
    service: str = Field(min_length=1, max_length=100)
    severity: Literal["low", "medium", "high", "critical"]
    root_cause: str = Field(min_length=1, max_length=200)


class IncidentAnalyticsArguments(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    operation: Literal[
        "count_by_root_cause",
        "recurrence",
        "date_range",
        "severity_by_service",
    ]
    records: tuple[IncidentRecord, ...] = Field(min_length=1, max_length=500)
    limit: int = Field(default=20, ge=1, le=100)


class McpReadArguments(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    operation: Literal["employee_directory", "service_catalog", "incident_record"]
    identifier: str = Field(min_length=1, max_length=100)
