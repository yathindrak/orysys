from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from orysys.application.conversations import Conversation
from orysys.domain.memory import MemoryItem, MemoryKind
from orysys.domain.tools import ToolResult


class CreateConversationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation: Conversation


class SendMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    message: str = Field(min_length=1, max_length=8_000)


class ProposeMemoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: MemoryKind
    content: str = Field(min_length=1, max_length=1_000)
    purpose: str = Field(min_length=1, max_length=500)
    provenance_run_id: str = Field(min_length=1)
    expires_at: datetime


class MemoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory: MemoryItem


class MemoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memories: tuple[MemoryItem, ...]


class ExecuteToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arguments: dict[str, object] = Field(default_factory=dict)
    idempotency_key: str = Field(default_factory=lambda: str(uuid4()), min_length=1)


class ToolListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tools: tuple[str, ...]


class ToolResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: ToolResult


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    retryable: bool = False
