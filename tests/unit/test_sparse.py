from pathlib import Path

from orysys.ingestion.sparse import PineconeBM25Encoder


def test_bm25_is_fitted_on_supplied_corpus_and_can_be_persisted(tmp_path: Path) -> None:
    encoder = PineconeBM25Encoder()
    encoder.fit(["PAY-DB-042 database saturation", "settlement poison record"])

    vectors = encoder.encode_documents(["PAY-DB-042 database saturation"])
    output = tmp_path / "bm25.json"
    encoder.dump(output)

    assert len(vectors) == 1
    assert vectors[0]["indices"]
    assert len(vectors[0]["indices"]) == len(vectors[0]["values"])
    assert output.exists()
