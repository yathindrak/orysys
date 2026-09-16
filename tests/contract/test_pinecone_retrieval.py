from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pinecone import AsyncIndex, AsyncPinecone

from orysys.adapters.fakes import DeterministicEmbeddingModel, IdentityReranker
from orysys.adapters.pinecone.retrieval import PineconeKnowledgeIndex
from orysys.domain.evidence import Evidence
from orysys.domain.identity import AccessScope
from orysys.ports.ingestion import SparseVector
from orysys.ports.retrieval import Reranker, SearchOptions


class FailingEmbeddingModel:
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        del texts
        raise RuntimeError("dense provider unavailable")


class QuerySparseEncoder:
    def fit(self, texts: Sequence[str]) -> None:
        del texts

    def encode_documents(self, texts: Sequence[str]) -> list[SparseVector]:
        del texts
        return []

    def encode_query(self, text: str) -> SparseVector:
        del text
        return {"indices": [10], "values": [2.0]}

    def dump(self, path: Path) -> None:
        del path


class FailingSparseEncoder(QuerySparseEncoder):
    def encode_query(self, text: str) -> SparseVector:
        del text
        raise RuntimeError("sparse encoder unavailable")


class RecordingIndex:
    def __init__(self) -> None:
        self.query_kwargs: dict[str, Any] = {}

    async def query(self, **kwargs: Any) -> object:
        self.query_kwargs = kwargs
        metadata = {
            "document_id": "incident-pay-2025-0214",
            "chunk_id": "chunk-1",
            "title": "Incident",
            "section": "Root cause",
            "chunk_text": "Connection pool exhaustion caused PAY-DB-042.",
            "source_uri": "orysys://incident",
            "content_hash": "hash",
            "corpus_version": "v1",
        }
        match = SimpleNamespace(id="record-1", score=0.8, metadata=metadata)
        return SimpleNamespace(matches=[match])

    async def close(self) -> None:
        return None


class RecordingClient:
    async def close(self) -> None:
        return None


class FailingReranker(Reranker):
    async def rerank(
        self, query: str, candidates: tuple[Evidence, ...], limit: int
    ) -> tuple[Evidence, ...]:
        del query, candidates, limit
        raise RuntimeError("reranker unavailable")


@pytest.mark.asyncio
async def test_hybrid_query_applies_weighting_scope_and_evidence_mapping() -> None:
    index = RecordingIndex()
    retriever = PineconeKnowledgeIndex(
        client=cast(AsyncPinecone, RecordingClient()),
        index=cast(AsyncIndex, index),
        embedding_model=DeterministicEmbeddingModel(dimension=2),
        sparse_encoder=QuerySparseEncoder(),
        reranker=IdentityReranker(),
    )
    scope = AccessScope(
        namespace="tenant-a",
        metadata_filter={"access_level": {"$lte": 2}},
        allowed_tools=frozenset(),
    )

    result = await retriever.search(
        "payment error", scope, SearchOptions(limit=1, candidate_count=5, alpha=0.25)
    )

    assert index.query_kwargs["namespace"] == "tenant-a"
    assert index.query_kwargs["filter"] == scope.metadata_filter
    assert index.query_kwargs["top_k"] == 5
    assert index.query_kwargs["sparse_vector"] == {"indices": [10], "values": [1.5]}
    assert result.evidence[0].document_id == "incident-pay-2025-0214"
    assert result.evidence[0].hybrid_score == 0.8
    assert not result.degraded


@pytest.mark.asyncio
async def test_reranker_failure_preserves_hybrid_order() -> None:
    retriever = PineconeKnowledgeIndex(
        client=cast(AsyncPinecone, RecordingClient()),
        index=cast(AsyncIndex, RecordingIndex()),
        embedding_model=DeterministicEmbeddingModel(dimension=2),
        sparse_encoder=QuerySparseEncoder(),
        reranker=FailingReranker(),
    )
    scope = AccessScope(
        namespace="tenant-a",
        metadata_filter={},
        allowed_tools=frozenset(),
    )

    result = await retriever.search("payment error", scope, SearchOptions(limit=1))

    assert result.degraded
    assert result.evidence[0].evidence_id == "record-1"


@pytest.mark.asyncio
async def test_dense_failure_uses_sparse_only_and_marks_degraded() -> None:
    index = RecordingIndex()
    retriever = PineconeKnowledgeIndex(
        client=cast(AsyncPinecone, RecordingClient()),
        index=cast(AsyncIndex, index),
        embedding_model=FailingEmbeddingModel(),
        sparse_encoder=QuerySparseEncoder(),
        reranker=IdentityReranker(),
        expected_dimensions=2,
    )

    result = await retriever.search(
        "payment error",
        AccessScope(namespace="tenant-a", metadata_filter={}, allowed_tools=frozenset()),
        SearchOptions(limit=1),
    )

    assert result.degraded
    assert index.query_kwargs["vector"] == [0.0, 0.0]
    assert index.query_kwargs["sparse_vector"] == {"indices": [10], "values": [2.0]}


@pytest.mark.asyncio
async def test_sparse_failure_uses_dense_only_and_marks_degraded() -> None:
    index = RecordingIndex()
    retriever = PineconeKnowledgeIndex(
        client=cast(AsyncPinecone, RecordingClient()),
        index=cast(AsyncIndex, index),
        embedding_model=DeterministicEmbeddingModel(dimension=2),
        sparse_encoder=FailingSparseEncoder(),
        reranker=IdentityReranker(),
    )

    result = await retriever.search(
        "payment error",
        AccessScope(namespace="tenant-a", metadata_filter={}, allowed_tools=frozenset()),
        SearchOptions(limit=1),
    )

    assert result.degraded
    assert index.query_kwargs["sparse_vector"] is None
    assert index.query_kwargs["vector"] != [0.0, 0.0]
