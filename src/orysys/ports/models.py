from collections.abc import AsyncIterator, Sequence
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ModelMessage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    role: MessageRole
    content: str = Field(min_length=1)


class ModelRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    messages: tuple[ModelMessage, ...] = Field(min_length=1)
    response_schema: dict[str, object] | None = None
    max_tokens: int | None = Field(default=None, ge=1)


class ModelResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    model: str


class ChatModel(Protocol):
    async def complete(self, request: ModelRequest) -> ModelResult: ...

    def stream(self, request: ModelRequest) -> AsyncIterator[str]: ...


class EmbeddingModel(Protocol):
    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...
