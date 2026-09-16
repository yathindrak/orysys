import asyncio
import operator
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Any, TypedDict, cast
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from orysys.adapters.telemetry import NoopTelemetry
from orysys.application.assistant import AssistantRequest, AssistantRuntime
from orysys.domain.events import ActivityEvent, EventType
from orysys.domain.evidence import Claim, Evidence, GroundedAnswer
from orysys.domain.identity import AccessScope, Principal
from orysys.domain.plans import ResearchPlan
from orysys.domain.policy import derive_access_scope
from orysys.domain.research import Finding, ResearchBatch, WorkerOutcome, WorkerStatus
from orysys.domain.validation import ValidationResult, validate_answer_citations
from orysys.graph.runtime import AssistantRunResult, DirectAssistantRuntime
from orysys.ports.research import ResearchPlanner, ResearchWorker
from orysys.ports.retrieval import KnowledgeIndex, SearchOptions
from orysys.ports.services import Telemetry


class ResearchState(TypedDict, total=False):
    request: AssistantRequest
    principal: Principal
    run_id: str
    scope: AccessScope
    plan: ResearchPlan
    evidence: tuple[Evidence, ...]
    batches: tuple[ResearchBatch, ...]
    outcomes: Annotated[list[WorkerOutcome], operator.add]
    findings: tuple[Finding, ...]
    selected_evidence: tuple[Evidence, ...]
    recursion_depth: int
    final_answer: GroundedAnswer
    validations: Annotated[list[ValidationResult], operator.add]
    events: Annotated[list[ActivityEvent], operator.add]


class WorkerInput(TypedDict):
    objective: str
    batch: ResearchBatch
    deadline: datetime


class ResearchNodes:
    def __init__(
        self,
        *,
        planner: ResearchPlanner,
        worker: ResearchWorker,
        knowledge_index: KnowledgeIndex,
    ) -> None:
        self._planner = planner
        self._worker = worker
        self._index = knowledge_index

    async def plan(self, state: ResearchState) -> ResearchState:
        plan = await self._planner.plan(state["request"].message)
        return {
            "scope": _research_scope(
                derive_access_scope(state["principal"]), state["request"].message
            ),
            "plan": plan,
            "recursion_depth": 0,
            "events": _events(
                state,
                (EventType.RUN_STARTED, None, {"status": "started"}),
                (EventType.NODE_STARTED, "research_plan", {}),
                (
                    EventType.RESEARCH_PLANNED,
                    "research_plan",
                    {
                        "query_count": len(plan.discovery_queries),
                        "max_children": plan.budget.max_children,
                        "max_depth": plan.budget.max_depth,
                    },
                ),
                (EventType.NODE_COMPLETED, "research_plan", {"route": "research"}),
            ),
        }

    async def discover(self, state: ResearchState) -> ResearchState:
        plan = state["plan"]
        queries = plan.discovery_queries[: plan.budget.max_retrieval_calls]

        async def search(query: str) -> tuple[Evidence, ...]:
            try:
                result = await self._index.search(
                    query,
                    state["scope"],
                    SearchOptions(limit=12, candidate_count=28, alpha=0.5),
                )
                return result.evidence
            except Exception:
                return ()

        results = await asyncio.gather(*(search(query) for query in queries))
        evidence_by_id = {item.evidence_id: item for result in results for item in result}
        evidence = tuple(evidence_by_id[key] for key in sorted(evidence_by_id))
        if "cause" in state["request"].message.casefold():
            root_causes = tuple(
                item
                for item in evidence
                if item.section and "root cause" in item.section.casefold()
            )
            if root_causes:
                evidence = root_causes
        return {
            "evidence": evidence,
            "events": _events(
                state,
                (EventType.NODE_STARTED, "research_discover", {}),
                (EventType.RETRIEVAL_STARTED, "research_discover", {}),
                (
                    EventType.RETRIEVAL_COMPLETED,
                    "research_discover",
                    {"evidence_count": len(evidence), "query_count": len(queries)},
                ),
                (EventType.NODE_COMPLETED, "research_discover", {}),
            ),
        }

    async def partition(self, state: ResearchState) -> ResearchState:
        documents: dict[str, list[Evidence]] = {}
        for item in state.get("evidence", ()):
            documents.setdefault(item.document_id, []).append(item)
        document_ids = sorted(documents)
        batch_size = state["plan"].batch_size
        batches = tuple(
            ResearchBatch(
                batch_id=f"batch-{start // batch_size + 1:02d}",
                evidence=tuple(
                    item
                    for document_id in document_ids[start : start + batch_size]
                    for item in documents[document_id]
                ),
            )
            for start in range(0, len(document_ids), batch_size)
        )[: state["plan"].budget.max_children]
        return {
            "batches": batches,
            "events": _events(
                state,
                (EventType.NODE_STARTED, "research_partition", {}),
                (
                    EventType.NODE_COMPLETED,
                    "research_partition",
                    {"batch_count": len(batches)},
                ),
            ),
        }

    async def worker(self, state: WorkerInput) -> dict[str, list[WorkerOutcome]]:
        batch = state["batch"]
        if datetime.now(UTC) >= state["deadline"]:
            outcome = _failed_outcome(batch, "The research deadline was reached.")
        else:
            try:
                outcome = await self._worker.analyze(state["objective"], batch)
            except Exception:
                outcome = _failed_outcome(batch, "This research batch could not be analyzed.")
        return {"outcomes": [outcome]}

    async def reduce(self, state: ResearchState) -> ResearchState:
        latest: dict[str, WorkerOutcome] = {}
        for outcome in sorted(
            state.get("outcomes", []), key=lambda item: (item.batch_id, item.attempt)
        ):
            latest[outcome.batch_id] = outcome
        successful = [item for item in latest.values() if item.status is not WorkerStatus.FAILURE]
        grouped_findings: dict[str, list[Finding]] = {}
        evidence_by_id: dict[str, Evidence] = {}
        for outcome in successful:
            for finding in outcome.findings:
                grouped_findings.setdefault(_normalize_finding_key(finding.key), []).append(finding)
            for evidence in outcome.evidence:
                evidence_by_id[evidence.evidence_id] = evidence
        findings = tuple(
            Finding(
                key=key,
                statement=items[0].statement,
                evidence_ids=tuple(
                    sorted({evidence_id for item in items for evidence_id in item.evidence_ids})
                ),
            )
            for key, items in sorted(grouped_findings.items())
        )
        failures = sum(item.status is WorkerStatus.FAILURE for item in latest.values())
        return {
            "findings": findings,
            "selected_evidence": tuple(evidence_by_id[key] for key in sorted(evidence_by_id)),
            "events": _events(
                state,
                (
                    EventType.RESEARCH_BATCHES_COMPLETED,
                    "research_reduce",
                    {
                        "batch_count": len(latest),
                        "failed_batches": failures,
                        "finding_count": len(findings),
                    },
                ),
            ),
        }

    async def retry_gaps(self, state: ResearchState) -> ResearchState:
        latest = {item.batch_id: item for item in state.get("outcomes", [])}
        failed_ids = {
            batch_id
            for batch_id, outcome in latest.items()
            if outcome.status is WorkerStatus.FAILURE
        }
        retry_batches = [
            batch.model_copy(update={"attempt": 1})
            for batch in state["batches"]
            if batch.batch_id in failed_ids
        ]
        initial_model_calls = 1 + len(state["batches"])
        remaining_model_calls = max(0, state["plan"].budget.max_model_calls - initial_model_calls)
        retry_batches = retry_batches[:remaining_model_calls]

        async def retry(batch: ResearchBatch) -> WorkerOutcome:
            if datetime.now(UTC) >= state["plan"].budget.deadline:
                return _failed_outcome(batch, "The research deadline was reached.")
            try:
                return await self._worker.analyze(state["plan"].objective, batch)
            except Exception:
                return _failed_outcome(batch, "This research batch could not be analyzed.")

        results = await asyncio.gather(*(retry(batch) for batch in retry_batches))
        return {
            "outcomes": list(results),
            "recursion_depth": state.get("recursion_depth", 0) + 1,
            "events": _events(
                state,
                (
                    EventType.RESEARCH_RECURSION,
                    "research_retry_gaps",
                    {"depth": 1, "batch_count": len(retry_batches)},
                ),
            ),
        }

    async def compose(self, state: ResearchState) -> ResearchState:
        findings = state.get("findings", ())
        latest = {item.batch_id: item for item in state.get("outcomes", [])}
        incomplete = any(item.status is WorkerStatus.FAILURE for item in latest.values())
        if findings:
            claims = tuple(
                Claim(text=item.statement, evidence_ids=item.evidence_ids) for item in findings
            )
            summary = " ".join(item.statement for item in findings[:3])
            answer = GroundedAnswer(
                claims=claims,
                summary=summary,
                incomplete=incomplete,
            )
            validations = validate_answer_citations(
                tuple(claim.evidence_ids for claim in claims),
                {item.evidence_id for item in state.get("selected_evidence", ())},
            )
            if not all(item.passed for item in validations):
                answer = _safe_research_answer()
        else:
            answer = _safe_research_answer()
            validations = (
                ValidationResult(
                    rule="research.findings_available",
                    passed=False,
                    public_message="No supported research findings were available.",
                ),
            )
        specs: list[tuple[EventType, str | None, dict[str, object]]] = [
            (EventType.ANSWER_DELTA, "research_compose", {"text": chunk})
            for chunk in _chunks(answer.summary)
        ]
        specs.extend(
            [
                (
                    EventType.VALIDATION_COMPLETED,
                    "research_compose",
                    {
                        "passed": all(item.passed for item in validations),
                        "results": [item.model_dump(mode="json") for item in validations],
                    },
                ),
                (
                    EventType.ANSWER_COMPLETED,
                    "research_compose",
                    {
                        "answer": answer.model_dump(mode="json"),
                        "evidence": [
                            item.model_dump(mode="json")
                            for item in state.get("selected_evidence", ())
                        ],
                    },
                ),
                (
                    EventType.RUN_COMPLETED,
                    "research_compose",
                    {"status": "completed", "incomplete": answer.incomplete},
                ),
            ]
        )
        return {
            "final_answer": answer,
            "validations": list(validations),
            "events": _events(state, *specs),
        }


def dispatch_workers(state: ResearchState) -> list[Send] | str:
    if not state.get("batches"):
        return "compose"
    return [
        Send(
            "worker",
            {
                "objective": state["plan"].objective,
                "batch": batch,
                "deadline": state["plan"].budget.deadline,
            },
        )
        for batch in state["batches"]
    ]


def route_after_reduce(state: ResearchState) -> str:
    failures = any(item.status is WorkerStatus.FAILURE for item in state.get("outcomes", []))
    if failures and state.get("recursion_depth", 0) < state["plan"].budget.max_depth:
        return "retry_gaps"
    return "compose"


def build_research_graph(nodes: ResearchNodes) -> Any:
    builder = StateGraph(ResearchState)
    builder.add_node("plan", nodes.plan)
    builder.add_node("discover", nodes.discover)
    builder.add_node("partition", nodes.partition)
    builder.add_node("worker", cast(Any, nodes.worker), input_schema=WorkerInput)
    builder.add_node("reduce", nodes.reduce)
    builder.add_node("retry_gaps", nodes.retry_gaps)
    builder.add_node("compose", nodes.compose)
    builder.add_edge(START, "plan")
    builder.add_edge("plan", "discover")
    builder.add_edge("discover", "partition")
    builder.add_conditional_edges("partition", dispatch_workers)
    builder.add_edge("worker", "reduce")
    builder.add_conditional_edges(
        "reduce",
        route_after_reduce,
        {"retry_gaps": "retry_gaps", "compose": "compose"},
    )
    builder.add_edge("retry_gaps", "reduce")
    builder.add_edge("compose", END)
    return cast(Any, builder.compile())


class ResearchAssistantRuntime:
    def __init__(
        self,
        *,
        planner: ResearchPlanner,
        worker: ResearchWorker,
        knowledge_index: KnowledgeIndex,
        telemetry: Telemetry | None = None,
    ) -> None:
        self._graph = build_research_graph(
            ResearchNodes(planner=planner, worker=worker, knowledge_index=knowledge_index)
        )
        self._telemetry = telemetry or NoopTelemetry()

    async def run(self, request: AssistantRequest, principal: Principal) -> AssistantRunResult:
        run_id = str(uuid4())
        initial: ResearchState = {
            "request": request,
            "principal": principal,
            "run_id": run_id,
            "outcomes": [],
            "validations": [],
            "events": [],
        }
        async with self._telemetry.span(
            "orysys.research",
            {"request_id": request.request_id, "run_id": run_id, "route": "research"},
        ):
            async with asyncio.timeout(65):
                raw: dict[str, Any] = await self._graph.ainvoke(initial, {"max_concurrency": 4})
        state = cast(ResearchState, raw)
        return AssistantRunResult(
            run_id=run_id,
            answer=state["final_answer"],
            evidence=state.get("selected_evidence", ()),
            validations=tuple(state.get("validations", [])),
            events=tuple(state.get("events", [])),
        )

    async def stream(
        self, request: AssistantRequest, principal: Principal
    ) -> AsyncIterator[ActivityEvent]:
        result = await self.run(request, principal)
        for event in result.events:
            await self._telemetry.event(event)
            yield event


class RoutingAssistantRuntime:
    def __init__(
        self,
        *,
        direct: DirectAssistantRuntime,
        research: ResearchAssistantRuntime,
    ) -> None:
        self._direct = direct
        self._research = research

    async def run(self, request: AssistantRequest, principal: Principal) -> AssistantRunResult:
        runtime = self._research if is_research_request(request.message) else self._direct
        return await runtime.run(request, principal)

    def stream(
        self, request: AssistantRequest, principal: Principal
    ) -> AsyncIterator[ActivityEvent]:
        runtime: AssistantRuntime = (
            self._research if is_research_request(request.message) else self._direct
        )
        return runtime.stream(request, principal)


def is_research_request(message: str) -> bool:
    normalized = message.casefold()
    indicators = (
        "across",
        "annual",
        "all incidents",
        "compare",
        "recurring",
        "research",
        "trend",
        "year",
    )
    return any(indicator in normalized for indicator in indicators)


def _events(
    state: ResearchState,
    *specs: tuple[EventType, str | None, dict[str, object]],
) -> list[ActivityEvent]:
    request = state["request"]
    start = len(state.get("events", []))
    return [
        ActivityEvent(
            sequence=start + index,
            request_id=request.request_id,
            run_id=state["run_id"],
            thread_id=request.thread_id,
            type=event_type,
            node=node,
            public_payload=payload,
        )
        for index, (event_type, node, payload) in enumerate(specs)
    ]


def _chunks(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"\S+\s*", text)) or (text,)


def _safe_research_answer() -> GroundedAnswer:
    return GroundedAnswer(
        claims=(),
        summary="I could not produce supported research findings from the authorized evidence.",
        incomplete=True,
    )


def _failed_outcome(batch: ResearchBatch, message: str) -> WorkerOutcome:
    return WorkerOutcome(
        batch_id=batch.batch_id,
        attempt=batch.attempt,
        status=WorkerStatus.FAILURE,
        public_error=message,
    )


def _research_scope(scope: AccessScope, message: str) -> AccessScope:
    base_clauses = scope.metadata_filter.get("$and")
    clauses: list[dict[str, object]] = (
        list(base_clauses) if isinstance(base_clauses, list) else [scope.metadata_filter]
    )
    normalized = message.casefold()
    if "incident" in normalized or "outage" in normalized:
        clauses.append({"document_type": "incident"})
    year_match = re.search(r"\b(20\d{2})\b", message)
    if year_match:
        year = int(year_match.group(1))
        start = int(datetime(year, 1, 1, tzinfo=UTC).timestamp())
        end = int(datetime(year + 1, 1, 1, tzinfo=UTC).timestamp()) - 1
        clauses.append({"created_at_epoch": {"$gte": start, "$lte": end}})
    return scope.model_copy(update={"metadata_filter": {"$and": clauses}})


def _normalize_finding_key(key: str) -> str:
    normalized = key.casefold().replace("-", "_").replace(" ", "_")
    if any(term in normalized for term in ("postgres", "connection_pool", "saturation")):
        return "database_connection_saturation"
    if any(term in normalized for term in ("poison", "malformed", "dead_letter")):
        return "poison_record_processing"
    return normalized[:120]
