from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    section: str | None = None
    page: int | None = Field(default=None, ge=1)
    excerpt: str = Field(min_length=1, max_length=2_000)
    source_uri: HttpUrl | str
    content_hash: str = Field(min_length=1)
    corpus_version: str = Field(min_length=1)
    hybrid_score: float | None = None
    rerank_score: float | None = None


class Claim(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = Field(min_length=1)


class GroundedAnswer(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claims: tuple[Claim, ...]
    summary: str = Field(min_length=1)
    incomplete: bool = False
