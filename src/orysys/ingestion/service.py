from collections import defaultdict
from pathlib import Path

from orysys.domain.ingestion import DocumentChunk, IngestionReport
from orysys.ingestion.chunking import DEFAULT_CHUNKING_CONFIG, ChunkingConfig, chunk_document
from orysys.ingestion.loaders import load_manifest
from orysys.ports.ingestion import SparseEncoder, SparseVector, VectorIndexWriter
from orysys.ports.models import EmbeddingModel


class DocumentIngestion:
    def __init__(
        self,
        embedding_model: EmbeddingModel,
        sparse_encoder: SparseEncoder,
        index_writer: VectorIndexWriter,
        *,
        chunking: ChunkingConfig = DEFAULT_CHUNKING_CONFIG,
    ) -> None:
        self._embedding_model = embedding_model
        self._sparse_encoder = sparse_encoder
        self._index_writer = index_writer
        self._chunking = chunking

    async def ingest(self, manifest_path: Path, bm25_output_path: Path) -> IngestionReport:
        documents = load_manifest(manifest_path)
        chunks = tuple(
            chunk for document in documents for chunk in chunk_document(document, self._chunking)
        )
        texts = [chunk.text for chunk in chunks]
        self._sparse_encoder.fit(texts)
        sparse_vectors = self._sparse_encoder.encode_documents(texts)
        self._sparse_encoder.dump(bm25_output_path)
        dense_vectors = await self._embedding_model.embed(texts)
        if len(dense_vectors) != len(chunks) or len(sparse_vectors) != len(chunks):
            raise ValueError("Encoder output count does not match chunk count")

        grouped: dict[str, list[tuple[DocumentChunk, list[float], SparseVector]]] = defaultdict(
            list
        )
        for chunk, dense, sparse in zip(chunks, dense_vectors, sparse_vectors, strict=True):
            grouped[chunk.document_id].append((chunk, dense, sparse))

        inserted = unchanged = deleted = 0
        for group in grouped.values():
            group_chunks = [item[0] for item in group]
            result = await self._index_writer.upsert_document(
                group_chunks[0].tenant_id,
                group_chunks,
                [item[1] for item in group],
                [item[2] for item in group],
            )
            inserted += result.inserted
            unchanged += result.unchanged
            deleted += result.deleted
        return IngestionReport(
            corpus_version=documents[0].corpus_version,
            documents=len(documents),
            chunks=len(chunks),
            inserted=inserted,
            unchanged=unchanged,
            deleted=deleted,
        )
