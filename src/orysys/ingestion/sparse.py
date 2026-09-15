from collections.abc import Sequence
from pathlib import Path
from typing import cast

from pinecone_text.sparse import BM25Encoder

from orysys.ports.ingestion import SparseVector


class PineconeBM25Encoder:
    def __init__(self) -> None:
        self._encoder = BM25Encoder()

    def fit(self, texts: Sequence[str]) -> None:
        self._encoder.fit(list(texts))

    def encode_documents(self, texts: Sequence[str]) -> list[SparseVector]:
        encoded = self._encoder.encode_documents(list(texts))
        if not isinstance(encoded, list):
            encoded = [encoded]
        return [cast(SparseVector, vector) for vector in encoded]

    def dump(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._encoder.dump(str(path))
