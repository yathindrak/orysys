from pydantic import BaseModel, ConfigDict, Field


class RateLimitDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed: bool
    retry_after_seconds: int | None = Field(default=None, ge=1)
    remaining: float = Field(ge=0)
