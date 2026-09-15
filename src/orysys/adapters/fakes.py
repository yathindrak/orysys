from collections import defaultdict
from collections.abc import AsyncIterator, Sequence

from orysys.domain.evidence import Evidence
from orysys.domain.identity import AccessScope
from orysys.domain.ingestion import DocumentChunk, IndexWriteResult
from orysys.ports.ingestion import SparseVector
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


class InMemoryVectorWriter:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, DocumentChunk]] = defaultdict(dict)

    async def upsert_document(
        self,
        namespace: str,
        chunks: Sequence[DocumentChunk],
        dense_vectors: Sequence[Sequence[float]],
        sparse_vectors: Sequence[SparseVector],
    ) -> IndexWriteResult:
        if len(chunks) != len(dense_vectors) or len(chunks) != len(sparse_vectors):
            raise ValueError("Chunk and vector counts must match")
        current = self.records[namespace]
        prefix = f"{chunks[0].document_id}:" if chunks else ""
        existing = {record_id for record_id in current if record_id.startswith(prefix)}
        incoming = {chunk.vector_id for chunk in chunks}
        for stale_id in existing - incoming:
            del current[stale_id]
        for chunk in chunks:
            current[chunk.vector_id] = chunk
        return IndexWriteResult(
            inserted=len(incoming - existing),
            unchanged=len(incoming & existing),
            deleted=len(existing - incoming),
        )
