import hashlib
import json
from pathlib import Path

from pydantic import TypeAdapter
from pypdf import PdfReader

from orysys.domain.ingestion import (
    CorpusManifest,
    DocumentElement,
    DocumentSpec,
    SourceDocument,
)

_MANIFEST_ADAPTER = TypeAdapter(CorpusManifest)


def load_manifest(path: Path) -> tuple[SourceDocument, ...]:
    manifest_path = path.resolve()
    manifest = _MANIFEST_ADAPTER.validate_json(manifest_path.read_text(encoding="utf-8"))
    root = manifest_path.parent
    seen: set[str] = set()
    documents: list[SourceDocument] = []
    for spec in manifest.documents:
        if spec.document_id in seen:
            raise ValueError(f"Duplicate document ID: {spec.document_id}")
        seen.add(spec.document_id)
        source_path = (root / spec.path).resolve()
        if not source_path.is_relative_to(root):
            raise ValueError(f"Document path escapes manifest directory: {spec.path}")
        documents.append(load_document(source_path, spec, manifest.corpus_version))
    return tuple(documents)


def load_document(path: Path, spec: DocumentSpec, corpus_version: str) -> SourceDocument:
    suffix = path.suffix.casefold()
    if suffix in {".md", ".markdown"}:
        elements = _parse_markdown(path.read_text(encoding="utf-8"))
    elif suffix == ".txt":
        elements = (DocumentElement(text=path.read_text(encoding="utf-8").strip()),)
    elif suffix == ".json":
        elements = _parse_json(path)
    elif suffix == ".pdf":
        elements = _parse_pdf(path)
    else:
        raise ValueError(f"Unsupported document type: {suffix or '<none>'}")
    if not elements:
        raise ValueError(f"Document contains no extractable text: {path.name}")
    canonical = "\n\n".join(element.text for element in elements)
    return SourceDocument(
        spec=spec,
        corpus_version=corpus_version,
        content_hash=_sha256(canonical),
        elements=elements,
    )


def _parse_markdown(content: str) -> tuple[DocumentElement, ...]:
    elements: list[DocumentElement] = []
    section: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        text = "\n".join(buffer).strip()
        if text:
            elements.append(DocumentElement(text=text, section=section))
        buffer.clear()

    for line in content.splitlines():
        if line.startswith("#") and line.lstrip("#").startswith(" "):
            flush()
            section = line.lstrip("#").strip()
        else:
            buffer.append(line)
    flush()
    return tuple(elements)


def _parse_json(path: Path) -> tuple[DocumentElement, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    sections = payload.get("sections") if isinstance(payload, dict) else None
    if not isinstance(sections, list):
        raise ValueError(f"JSON document must contain a sections list: {path.name}")
    return tuple(
        DocumentElement(text=str(item["text"]).strip(), section=str(item.get("title") or "JSON"))
        for item in sections
        if isinstance(item, dict) and str(item.get("text") or "").strip()
    )


def _parse_pdf(path: Path) -> tuple[DocumentElement, ...]:
    reader = PdfReader(path)
    elements = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            elements.append(DocumentElement(text=text, page=page_number))
    return tuple(elements)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
