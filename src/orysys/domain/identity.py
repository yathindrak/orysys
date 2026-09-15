from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Role(StrEnum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    ADMINISTRATOR = "administrator"


class Principal(BaseModel):
    """Identity produced by a trusted verifier, never from ordinary request fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    subject: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    roles: frozenset[Role] = Field(min_length=1)
    departments: frozenset[str] = Field(default_factory=frozenset)
    clearance: int = Field(default=0, ge=0, le=10)


class AccessScope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    namespace: str = Field(min_length=1)
    metadata_filter: dict[str, object]
    allowed_tools: frozenset[str]
