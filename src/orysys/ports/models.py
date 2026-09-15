from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class ModelRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    messages: tuple[str, ...] = Field(min_length=1)
    response_schema: dict[str, object] | None = None


class ModelResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    model: str


class ChatModel(Protocol):
    async def complete(self, request: ModelRequest) -> ModelResult: ...

    def stream(self, request: ModelRequest) -> AsyncIterator[str]: ...


class EmbeddingModel(Protocol):
    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...
