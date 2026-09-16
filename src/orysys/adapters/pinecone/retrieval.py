from typing import Any

from pinecone import AsyncIndex, AsyncPinecone
from pydantic import BaseModel, ConfigDict, Field

from orysys.domain.errors import ProviderUnavailable
from orysys.domain.evidence import Evidence
from orysys.domain.identity import AccessScope
from orysys.ports.ingestion import SparseEncoder, SparseVector
from orysys.ports.models import EmbeddingModel
from orysys.ports.retrieval import KnowledgeIndex, Reranker, SearchOptions, SearchResult


class _MatchMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    document_id: str
    chunk_id: str
    title: str
    section: str | None = None
    page: int | None = Field(default=None, ge=1)
    chunk_text: str
    source_uri: str
    content_hash: str
    corpus_version: str


class PineconeKnowledgeIndex(KnowledgeIndex):
    def __init__(
        self,
        *,
        client: AsyncPinecone,
        index: AsyncIndex,
        embedding_model: EmbeddingModel,
        sparse_encoder: SparseEncoder,
        reranker: Reranker,
        expected_dimensions: int | None = None,
    ) -> None:
        self._client = client
        self._index = index
        self._embedding_model = embedding_model
        self._sparse_encoder = sparse_encoder
        self._reranker = reranker
        self._expected_dimensions = expected_dimensions

    @classmethod
    async def connect(
        cls,
        *,
        api_key: str,
        index_name: str,
        expected_dimensions: int,
        embedding_model: EmbeddingModel,
        sparse_encoder: SparseEncoder,
        reranker: Reranker,
    ) -> "PineconeKnowledgeIndex":
        client = AsyncPinecone(api_key=api_key)
        description = await client.describe_index(index_name)
        if description.dimension != expected_dimensions:
            await client.close()
            raise ValueError(
                f"Pinecone dimension mismatch: expected {expected_dimensions}, "
                f"got {description.dimension}"
            )
        if description.metric != "dotproduct" or description.vector_type != "dense":
            await client.close()
            raise ValueError("Pinecone index must be a dense dotproduct index")
        if not description.host:
            await client.close()
            raise ValueError("Pinecone did not return an index host")
        index = await client.index(host=description.host)
        return cls(
            client=client,
            index=index,
            embedding_model=embedding_model,
            sparse_encoder=sparse_encoder,
            reranker=reranker,
            expected_dimensions=expected_dimensions,
        )

    async def search(self, query: str, scope: AccessScope, options: SearchOptions) -> SearchResult:
        degraded = False
        weighted_dense: list[float]
        sparse_query: SparseVector | None
        try:
            dense = (await self._embedding_model.embed([query]))[0]
        except Exception as dense_error:
            try:
                sparse = self._sparse_encoder.encode_query(query)
            except Exception as sparse_error:
                raise ProviderUnavailable("query encoding") from sparse_error
            if self._expected_dimensions is None:
                raise ProviderUnavailable("dense query encoding") from dense_error
            weighted_dense = [0.0] * self._expected_dimensions
            sparse_query = sparse
            degraded = True
        else:
            try:
                sparse = self._sparse_encoder.encode_query(query)
            except Exception:
                sparse_query = None
                weighted_dense = dense
                degraded = True
            else:
                weighted_dense = [value * options.alpha for value in dense]
                weighted_sparse = _weight_sparse(sparse, 1 - options.alpha)
                sparse_query = weighted_sparse if options.alpha < 1 else None
        try:
            response = await self._index.query(
                namespace=scope.namespace,
                vector=weighted_dense,
                sparse_vector=sparse_query,
                filter=scope.metadata_filter,
                top_k=options.candidate_count,
                include_metadata=True,
                include_values=False,
            )
        except Exception as error:
            raise ProviderUnavailable("Pinecone retrieval") from error

        evidence = tuple(
            _to_evidence(match.id, match.score, match.metadata)
            for match in response.matches
            if match.id and match.metadata
        )
        try:
            ranked = await self._reranker.rerank(query, evidence, options.limit)
        except Exception:
            ranked = evidence[: options.limit]
            degraded = True
        return SearchResult(evidence=ranked, degraded=degraded)

    async def close(self) -> None:
        await self._index.close()
        await self._client.close()


def _weight_sparse(vector: SparseVector, weight: float) -> SparseVector:
    return {
        "indices": vector["indices"],
        "values": [value * weight for value in vector["values"]],
    }


def _to_evidence(record_id: str, score: float | None, metadata: dict[str, Any]) -> Evidence:
    parsed = _MatchMetadata.model_validate(metadata)
    return Evidence(
        evidence_id=record_id,
        document_id=parsed.document_id,
        chunk_id=parsed.chunk_id,
        title=parsed.title,
        section=parsed.section,
        page=parsed.page,
        excerpt=parsed.chunk_text,
        source_uri=parsed.source_uri,
        content_hash=parsed.content_hash,
        corpus_version=parsed.corpus_version,
        hybrid_score=score,
    )
