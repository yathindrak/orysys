import hashlib
import re
from dataclasses import dataclass

from orysys.domain.ingestion import DocumentChunk, SourceDocument

_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")


@dataclass(frozen=True, slots=True)
class ChunkingConfig:
    target_characters: int = 1_400
    overlap_characters: int = 180

    def __post_init__(self) -> None:
        if self.target_characters < 200:
            raise ValueError("target_characters must be at least 200")
        if not 0 <= self.overlap_characters < self.target_characters:
            raise ValueError("overlap_characters must be smaller than target_characters")


DEFAULT_CHUNKING_CONFIG = ChunkingConfig()


def chunk_document(
    document: SourceDocument, config: ChunkingConfig = DEFAULT_CHUNKING_CONFIG
) -> tuple[DocumentChunk, ...]:
    chunks: list[DocumentChunk] = []
    ordinal = 0
    for element in document.elements:
        for text in _split_text(element.text, config):
            content_hash = _sha256(text)
            chunk_id = _sha256(
                "\0".join(
                    (
                        document.spec.document_id,
                        document.spec.version,
                        element.section or "",
                        str(element.page or ""),
                        str(ordinal),
                        content_hash,
                    )
                )
            )[:24]
            chunks.append(
                DocumentChunk(
                    vector_id=f"{document.spec.document_id}:{chunk_id}",
                    chunk_id=chunk_id,
                    document_id=document.spec.document_id,
                    version=document.spec.version,
                    title=document.spec.title,
                    tenant_id=document.spec.tenant_id,
                    department=document.spec.department,
                    document_type=document.spec.document_type,
                    access_level=document.spec.access_level,
                    created_date=document.spec.created_date,
                    source_uri=document.spec.source_uri,
                    corpus_version=document.corpus_version,
                    document_hash=document.content_hash,
                    content_hash=content_hash,
                    section=element.section,
                    page=element.page,
                    text=text,
                )
            )
            ordinal += 1
    return tuple(chunks)


def _split_text(text: str, config: ChunkingConfig) -> tuple[str, ...]:
    paragraphs = [part.strip() for part in _PARAGRAPH_BREAK.split(text) if part.strip()]
    atomic: list[str] = []
    for paragraph in paragraphs:
        atomic.extend(_split_oversized(paragraph, config.target_characters))

    chunks: list[str] = []
    current = ""
    for paragraph in atomic:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if current and len(candidate) > config.target_characters:
            chunks.append(current)
            overlap = _tail(current, config.overlap_characters)
            current = f"{overlap}\n\n{paragraph}".strip() if overlap else paragraph
        else:
            current = candidate
    if current:
        chunks.append(current)
    return tuple(chunks)


def _split_oversized(text: str, limit: int) -> list[str]:
    words = text.split()
    parts: list[str] = []
    current: list[str] = []
    for word in words:
        if current and len(" ".join((*current, word))) > limit:
            parts.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        parts.append(" ".join(current))
    return parts


def _tail(text: str, limit: int) -> str:
    if limit == 0:
        return ""
    words = text.split()
    selected: list[str] = []
    for word in reversed(words):
        candidate = " ".join(reversed((*selected, word)))
        if len(candidate) > limit:
            break
        selected.append(word)
    return " ".join(reversed(selected))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
