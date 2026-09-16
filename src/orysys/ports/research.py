from typing import Protocol

from orysys.domain.plans import ResearchPlan
from orysys.domain.research import ResearchBatch, WorkerOutcome


class ResearchPlanner(Protocol):
    async def plan(self, question: str) -> ResearchPlan: ...


class ResearchWorker(Protocol):
    async def analyze(self, objective: str, batch: ResearchBatch) -> WorkerOutcome: ...
