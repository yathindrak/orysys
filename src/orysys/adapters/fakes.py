from collections.abc import AsyncIterator, Sequence

from orysys.domain.evidence import Evidence
from orysys.domain.identity import AccessScope
from orysys.ports.models import ModelRequest, ModelResult
from orysys.ports.retrieval import SearchOptions, SearchResult


class ScriptedChatModel:
    def __init__(self, response: str, *, model: str = "scripted-test-model") -> None:
        self._response = response
        self._model = model

    async def complete(self, request: ModelRequest) -> ModelResult:
        del request
        return ModelResult(text=self._response, model=self._model)

    async def stream(self, request: ModelRequest) -> AsyncIterator[str]:
        del request
        for token in self._response.split():
            yield f"{token} "


class DeterministicEmbeddingModel:
    def __init__(self, dimension: int = 8) -> None:
        self._dimension = dimension

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        for index, byte in enumerate(text.encode("utf-8")):
            vector[index % self._dimension] += byte / 255
        return vector


class InMemoryKnowledgeIndex:
    def __init__(self, evidence: Sequence[Evidence] = ()) -> None:
        self._evidence = tuple(evidence)

    async def search(self, query: str, scope: AccessScope, options: SearchOptions) -> SearchResult:
        del scope
        terms = {term.casefold() for term in query.split()}
        ranked = sorted(
            self._evidence,
            key=lambda item: len(terms.intersection(item.excerpt.casefold().split())),
            reverse=True,
        )
        return SearchResult(evidence=tuple(ranked[: options.limit]))
