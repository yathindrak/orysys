from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Route(StrEnum):
    DIRECT_RETRIEVAL = "direct_retrieval"
    RESEARCH = "research"
    TOOL = "tool"


class RunBudget(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_depth: int = Field(default=1, ge=0, le=2)
    max_children: int = Field(default=4, ge=1, le=8)
    max_retrieval_calls: int = Field(default=6, ge=1, le=20)
    max_model_calls: int = Field(default=8, ge=1, le=24)
    token_budget: int = Field(default=12_000, ge=1_000, le=100_000)
    deadline: datetime


class ResearchPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    objective: str = Field(min_length=1, max_length=1_000)
    discovery_queries: tuple[str, ...] = Field(min_length=1, max_length=8)
    grouping_strategy: str = Field(min_length=1, max_length=100)
    batch_size: int = Field(default=5, ge=1, le=20)
    budget: RunBudget

    @model_validator(mode="after")
    def queries_are_unique(self) -> "ResearchPlan":
        if len(set(self.discovery_queries)) != len(self.discovery_queries):
            raise ValueError("discovery queries must be unique")
        return self
