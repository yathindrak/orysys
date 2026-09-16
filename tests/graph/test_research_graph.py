import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from orysys.adapters.fakes import InMemoryKnowledgeIndex
from orysys.application.assistant import AssistantRequest
from orysys.domain.events import EventType
from orysys.domain.evidence import Evidence
from orysys.domain.identity import Principal, Role
from orysys.domain.plans import ResearchPlan, RunBudget
from orysys.domain.research import Finding, ResearchBatch, WorkerOutcome, WorkerStatus
from orysys.research.runtime import ResearchAssistantRuntime


class FixedPlanner:
    async def plan(self, question: str) -> ResearchPlan:
        return ResearchPlan(
            objective=question,
            discovery_queries=("payment incidents 2025", "recurring payment outage causes"),
            grouping_strategy="document",
            batch_size=2,
            budget=RunBudget(
                max_depth=1,
                max_children=4,
                max_retrieval_calls=2,
                max_model_calls=8,
                token_budget=8_000,
                deadline=datetime.now(UTC) + timedelta(minutes=1),
            ),
        )


class RetryOneWorker:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def analyze(self, objective: str, batch: ResearchBatch) -> WorkerOutcome:
        del objective
        self.calls.append((batch.batch_id, batch.attempt))
        if batch.batch_id == "batch-02" and batch.attempt == 0:
            raise RuntimeError("simulated isolated worker failure")
        evidence = batch.evidence[0]
        return WorkerOutcome(
            batch_id=batch.batch_id,
            attempt=batch.attempt,
            status=WorkerStatus.SUCCESS,
            findings=(
                Finding(
                    key=f"cause-{batch.batch_id}",
                    statement=f"Supported finding from {evidence.document_id}.",
                    evidence_ids=(evidence.evidence_id,),
                ),
            ),
            evidence=batch.evidence,
        )


class AlwaysFailOneWorker(RetryOneWorker):
    async def analyze(self, objective: str, batch: ResearchBatch) -> WorkerOutcome:
        if batch.batch_id == "batch-02":
            self.calls.append((batch.batch_id, batch.attempt))
            raise RuntimeError("permanent isolated failure")
        return await super().analyze(objective, batch)


class SlowWorker:
    async def analyze(self, objective: str, batch: ResearchBatch) -> WorkerOutcome:
        del objective, batch
        await asyncio.sleep(1)
        raise AssertionError("deadline did not cancel slow worker")


class ShortDeadlinePlanner(FixedPlanner):
    async def plan(self, question: str) -> ResearchPlan:
        plan = await super().plan(question)
        return plan.model_copy(
            update={
                "budget": plan.budget.model_copy(
                    update={"deadline": datetime.now(UTC) + timedelta(milliseconds=10)}
                )
            }
        )


def _evidence(index: int) -> Evidence:
    return Evidence(
        evidence_id=f"ev-{index}",
        document_id=f"incident-{index}",
        chunk_id=f"chunk-{index}",
        title=f"Incident {index}",
        section="Root cause",
        excerpt=f"Root cause evidence {index}.",
        source_uri=f"https://example.test/incidents/{index}",
        content_hash=f"hash-{index}",
        corpus_version="test-v1",
    )


@pytest.mark.asyncio
async def test_research_fans_out_reduces_and_retries_one_failed_batch() -> None:
    worker = RetryOneWorker()
    runtime = ResearchAssistantRuntime(
        planner=FixedPlanner(),
        worker=worker,
        knowledge_index=InMemoryKnowledgeIndex([_evidence(index) for index in range(4)]),
    )
    request = AssistantRequest(
        request_id="request-1",
        thread_id="thread-1",
        message="Compare all annual incidents and identify recurring causes.",
    )
    principal = Principal(
        subject="analyst-1",
        tenant_id="tenant-1",
        roles=frozenset({Role.ANALYST}),
        departments=frozenset({"payments"}),
        clearance=3,
    )

    result = await runtime.run(request, principal)

    assert not result.answer.incomplete
    assert len(result.answer.claims) == 2
    assert ("batch-02", 0) in worker.calls
    assert ("batch-02", 1) in worker.calls
    assert any(event.type is EventType.RESEARCH_RECURSION for event in result.events)
    assert [event.sequence for event in result.events] == list(range(len(result.events)))
    assert result.events[-1].type is EventType.RUN_COMPLETED


@pytest.mark.asyncio
async def test_permanent_child_failure_does_not_cancel_successful_sibling() -> None:
    worker = AlwaysFailOneWorker()
    runtime = ResearchAssistantRuntime(
        planner=FixedPlanner(),
        worker=worker,
        knowledge_index=InMemoryKnowledgeIndex([_evidence(index) for index in range(4)]),
    )

    result = await runtime.run(
        AssistantRequest(
            request_id="request-partial",
            thread_id="thread-partial",
            message="Compare all annual incidents and identify recurring causes.",
        ),
        Principal(
            subject="analyst-1",
            tenant_id="tenant-1",
            roles=frozenset({Role.ANALYST}),
        ),
    )

    assert result.answer.incomplete
    assert len(result.answer.claims) == 1
    assert any(event.public_payload.get("failed_batches") == 1 for event in result.events)


@pytest.mark.asyncio
async def test_research_child_is_cancelled_at_plan_deadline() -> None:
    runtime = ResearchAssistantRuntime(
        planner=ShortDeadlinePlanner(),
        worker=SlowWorker(),
        knowledge_index=InMemoryKnowledgeIndex([_evidence(1)]),
        deadline_seconds=1,
    )

    result = await runtime.run(
        AssistantRequest(
            request_id="request-deadline",
            thread_id="thread-deadline",
            message="Research all annual incidents.",
        ),
        Principal(
            subject="analyst-1",
            tenant_id="tenant-1",
            roles=frozenset({Role.ANALYST}),
        ),
    )

    assert result.answer.incomplete
    assert not result.answer.claims
