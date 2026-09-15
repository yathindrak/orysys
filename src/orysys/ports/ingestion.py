from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, TypedDict

from orysys.domain.ingestion import DocumentChunk, IndexWriteResult


class SparseVector(TypedDict):
    indices: list[int]
    values: list[float]


class SparseEncoder(Protocol):
    def fit(self, texts: Sequence[str]) -> None: ...

    def encode_documents(self, texts: Sequence[str]) -> list[SparseVector]: ...

    def dump(self, path: Path) -> None: ...


class VectorIndexWriter(Protocol):
    async def upsert_document(
        self,
        namespace: str,
        chunks: Sequence[DocumentChunk],
        dense_vectors: Sequence[Sequence[float]],
        sparse_vectors: Sequence[SparseVector],
    ) -> IndexWriteResult: ...
