from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from orysys.domain.evidence import Evidence
from orysys.domain.identity import AccessScope


class SearchOptions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    limit: int = Field(default=8, ge=1, le=50)
    candidate_count: int = Field(default=30, ge=1, le=100)
    alpha: float = Field(default=0.5, ge=0, le=1)

    @model_validator(mode="after")
    def candidates_cover_limit(self) -> "SearchOptions":
        if self.candidate_count < self.limit:
            raise ValueError("candidate_count must be greater than or equal to limit")
        return self


class SearchResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence: tuple[Evidence, ...]
    degraded: bool = False


class KnowledgeIndex(Protocol):
    async def search(
        self, query: str, scope: AccessScope, options: SearchOptions
    ) -> SearchResult: ...


class Reranker(Protocol):
    async def rerank(
        self, query: str, candidates: tuple[Evidence, ...], limit: int
    ) -> tuple[Evidence, ...]: ...
