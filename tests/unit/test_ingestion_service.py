import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from orysys.adapters.fakes import DeterministicEmbeddingModel, InMemoryVectorWriter
from orysys.ingestion.service import DocumentIngestion
from orysys.ports.ingestion import SparseVector


class RecordingSparseEncoder:
    def __init__(self) -> None:
        self.fitted: tuple[str, ...] = ()

    def fit(self, texts: Sequence[str]) -> None:
        self.fitted = tuple(texts)

    def encode_documents(self, texts: Sequence[str]) -> list[SparseVector]:
        return [{"indices": [1], "values": [1.0]} for _ in texts]

    def encode_query(self, text: str) -> SparseVector:
        del text
        return {"indices": [1], "values": [1.0]}

    def dump(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"documents": len(self.fitted)}), encoding="utf-8")


@pytest.mark.asyncio
async def test_ingestion_is_idempotent_and_persists_sparse_parameters(tmp_path: Path) -> None:
    writer = InMemoryVectorWriter()
    sparse = RecordingSparseEncoder()
    service = DocumentIngestion(
        embedding_model=DeterministicEmbeddingModel(dimension=8),
        sparse_encoder=sparse,
        index_writer=writer,
    )
    bm25_path = tmp_path / "bm25.json"

    first = await service.ingest(Path("data/sample/manifest.json"), bm25_path)
    second = await service.ingest(Path("data/sample/manifest.json"), bm25_path)

    assert first.documents == 10
    assert first.chunks > 10
    assert first.inserted == first.chunks
    assert first.unchanged == 0
    assert second.inserted == 0
    assert second.unchanged == second.chunks
    assert second.deleted == 0
    assert bm25_path.exists()
