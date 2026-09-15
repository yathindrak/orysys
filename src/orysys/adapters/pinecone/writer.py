from collections.abc import Sequence

from pinecone import AsyncIndex, AsyncPinecone

from orysys.domain.ingestion import DocumentChunk, IndexWriteResult
from orysys.ports.ingestion import SparseVector


class PineconeVectorWriter:
    def __init__(self, client: AsyncPinecone, index: AsyncIndex) -> None:
        self._client = client
        self._index = index

    @classmethod
    async def connect(
        cls, *, api_key: str, index_name: str, expected_dimensions: int
    ) -> "PineconeVectorWriter":
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
        return cls(client, index)

    async def upsert_document(
        self,
        namespace: str,
        chunks: Sequence[DocumentChunk],
        dense_vectors: Sequence[Sequence[float]],
        sparse_vectors: Sequence[SparseVector],
    ) -> IndexWriteResult:
        if not chunks:
            return IndexWriteResult()
        if len(chunks) != len(dense_vectors) or len(chunks) != len(sparse_vectors):
            raise ValueError("Chunk and vector counts must match")
        prefix = f"{chunks[0].document_id}:"
        existing: set[str] = set()
        async for page in self._index.list(prefix=prefix, namespace=namespace):
            existing.update(item.id for item in page.vectors if item.id)
        incoming = {chunk.vector_id for chunk in chunks}
        new_ids = incoming - existing
        stale_ids = existing - incoming
        records = [
            {
                "id": chunk.vector_id,
                "values": list(dense),
                "sparse_values": sparse,
                "metadata": chunk.pinecone_metadata(),
            }
            for chunk, dense, sparse in zip(chunks, dense_vectors, sparse_vectors, strict=True)
            if chunk.vector_id in new_ids
        ]
        if records:
            await self._index.upsert(
                vectors=records,
                namespace=namespace,
                batch_size=100,
                show_progress=False,
                max_concurrency=4,
            )
        if stale_ids:
            await self._index.delete(ids=sorted(stale_ids), namespace=namespace)
        return IndexWriteResult(
            inserted=len(new_ids),
            unchanged=len(incoming & existing),
            deleted=len(stale_ids),
        )

    async def close(self) -> None:
        await self._index.close()
        await self._client.close()
