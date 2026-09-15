from datetime import UTC, date, datetime, time
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class DocumentType(StrEnum):
    POLICY = "policy"
    ARCHITECTURE = "architecture"
    RUNBOOK = "runbook"
    INCIDENT = "incident"
    PRODUCT_SPECIFICATION = "product_specification"
    MEETING_NOTE = "meeting_note"


class DocumentSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    version: str = Field(min_length=1, max_length=32)
    path: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    tenant_id: str = Field(min_length=1, max_length=64)
    department: str = Field(min_length=1, max_length=64)
    document_type: DocumentType
    access_level: int = Field(ge=0, le=10)
    created_date: date
    source_uri: str = Field(min_length=1, max_length=500)


class CorpusManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    corpus_version: str = Field(min_length=1, max_length=64)
    documents: tuple[DocumentSpec, ...] = Field(min_length=1)


class DocumentElement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1)
    section: str | None = None
    page: int | None = Field(default=None, ge=1)


class SourceDocument(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    spec: DocumentSpec
    corpus_version: str
    content_hash: str
    elements: tuple[DocumentElement, ...] = Field(min_length=1)


class DocumentChunk(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    vector_id: str
    chunk_id: str
    document_id: str
    version: str
    title: str
    tenant_id: str
    department: str
    document_type: DocumentType
    access_level: int
    created_date: date
    source_uri: str
    corpus_version: str
    document_hash: str
    content_hash: str
    section: str | None = None
    page: int | None = None
    text: str = Field(min_length=1)

    def pinecone_metadata(self) -> dict[str, str | int]:
        metadata: dict[str, str | int] = {
            "document_id": self.document_id,
            "version": self.version,
            "chunk_id": self.chunk_id,
            "title": self.title,
            "department": self.department,
            "document_type": self.document_type.value,
            "access_level": self.access_level,
            "created_date": self.created_date.isoformat(),
            "created_at_epoch": int(
                datetime.combine(self.created_date, time.min, tzinfo=UTC).timestamp()
            ),
            "source_uri": self.source_uri,
            "corpus_version": self.corpus_version,
            "document_hash": self.document_hash,
            "content_hash": self.content_hash,
            "chunk_text": self.text,
        }
        if self.section:
            metadata["section"] = self.section
        if self.page:
            metadata["page"] = self.page
        return metadata


class IndexWriteResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    inserted: int = 0
    unchanged: int = 0
    deleted: int = 0


class IngestionReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    corpus_version: str
    documents: int
    chunks: int
    inserted: int
    unchanged: int
    deleted: int
    rejected: int = 0
    failed: int = 0
