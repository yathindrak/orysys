from pathlib import Path

from orysys.ingestion.chunking import ChunkingConfig, chunk_document
from orysys.ingestion.loaders import load_manifest


def test_chunks_are_stable_attributed_and_bounded() -> None:
    document = load_manifest(Path("data/sample/manifest.json"))[2]
    config = ChunkingConfig(target_characters=300, overlap_characters=40)

    first = chunk_document(document, config)
    second = chunk_document(document, config)

    assert first == second
    assert all(chunk.vector_id.startswith(f"{document.spec.document_id}:") for chunk in first)
    assert all(len(chunk.text) <= 340 for chunk in first)
    assert all(chunk.document_hash == document.content_hash for chunk in first)
    assert all(chunk.section for chunk in first)


def test_chunk_metadata_contains_access_and_attribution() -> None:
    document = load_manifest(Path("data/sample/manifest.json"))[2]
    chunk = chunk_document(document)[0]

    metadata = chunk.pinecone_metadata()

    assert metadata["document_id"] == "incident-pay-2025-0214"
    assert metadata["department"] == "payments"
    assert metadata["access_level"] == 2
    assert metadata["chunk_id"] == chunk.chunk_id
    assert metadata["chunk_text"] == chunk.text
