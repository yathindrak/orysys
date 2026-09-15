import json
from pathlib import Path

import pytest

from orysys.ingestion.loaders import load_manifest


def test_sample_manifest_loads_with_stable_hashes() -> None:
    first = load_manifest(Path("data/sample/manifest.json"))
    second = load_manifest(Path("data/sample/manifest.json"))

    assert len(first) == 10
    assert [document.content_hash for document in first] == [
        document.content_hash for document in second
    ]
    assert all(document.elements for document in first)


def test_manifest_rejects_paths_outside_corpus(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("not allowed", encoding="utf-8")
    manifest = {
        "corpus_version": "test-v1",
        "documents": [
            {
                "document_id": "outside-document",
                "version": "1",
                "path": "../outside.txt",
                "title": "Outside",
                "tenant_id": "tenant",
                "department": "security",
                "document_type": "policy",
                "access_level": 1,
                "created_date": "2025-01-01",
                "source_uri": "orysys://test/outside",
            }
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="escapes manifest directory"):
        load_manifest(path)
