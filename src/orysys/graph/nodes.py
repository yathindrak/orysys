import json
import re
from typing import cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from orysys.domain.events import ActivityEvent, EventType
from orysys.domain.evidence import Claim, GroundedAnswer
from orysys.domain.policy import derive_access_scope
from orysys.domain.validation import ValidationResult, validate_answer_citations
from orysys.graph.prompts import SYSTEM_PROMPT, answer_prompt, repair_prompt
from orysys.graph.state import AssistantState
from orysys.observability import get_logger, redact
from orysys.ports.models import ChatModel, MessageRole, ModelMessage, ModelRequest
from orysys.ports.retrieval import KnowledgeIndex, SearchOptions

_SAFE_SUMMARY = "I could not produce a sufficiently supported answer from the authorized evidence."


class _AnswerDraft(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claims: tuple[Claim, ...] = Field(min_length=1)
    summary: str = Field(min_length=1)
    incomplete: bool = False


class DirectGraphNodes:
    def __init__(
        self,
        *,
        chat_model: ChatModel,
        knowledge_index: KnowledgeIndex,
        search_options: SearchOptions | None = None,
    ) -> None:
        self._chat_model = chat_model
        self._knowledge_index = knowledge_index
        self._search_options = search_options or SearchOptions()
        self._logger = get_logger()

    async def input_policy(self, state: AssistantState) -> AssistantState:
        scope = derive_access_scope(state["principal"])
        return {
            "access_scope": scope,
            "repair_count": 0,
            "events": self._events(
                state,
                (EventType.RUN_STARTED, None, {"status": "started"}),
                (EventType.NODE_STARTED, "input_policy", {}),
                (EventType.NODE_COMPLETED, "input_policy", {"authorized": True}),
            ),
        }

    async def understand_and_plan(self, state: AssistantState) -> AssistantState:
        return {
            "route": "direct_retrieval",
            "events": self._events(
                state,
                (EventType.NODE_STARTED, "understand_and_plan", {}),
                (
                    EventType.NODE_COMPLETED,
                    "understand_and_plan",
                    {"route": "direct_retrieval"},
                ),
            ),
        }

    async def retrieve(self, state: AssistantState) -> AssistantState:
        events = self._events(
            state,
            (EventType.NODE_STARTED, "retrieve", {}),
            (EventType.RETRIEVAL_STARTED, "retrieve", {}),
        )
        try:
            result = await self._knowledge_index.search(
                _retrieval_query(state),
                state["access_scope"],
                self._search_options,
            )
        except Exception as error:
            self._logger.warning(
                "retrieval_failed",
                **redact(
                    {
                        "request_id": state["request"].request_id,
                        "run_id": state["run_id"],
                        "error_type": type(error).__name__,
                    }
                ),
            )
            return {
                "evidence": (),
                "draft_error": "retrieval_unavailable",
                "events": events
                + self._events(
                    state,
                    (EventType.RETRIEVAL_DEGRADED, "retrieve", {"reason": "unavailable"}),
                    (EventType.NODE_COMPLETED, "retrieve", {"evidence_count": 0}),
                    offset=len(events),
                ),
            }
        return {
            "evidence": result.evidence,
            "events": events
            + self._events(
                state,
                (
                    EventType.RETRIEVAL_COMPLETED,
                    "retrieve",
                    {"evidence_count": len(result.evidence), "degraded": result.degraded},
                ),
                (EventType.NODE_COMPLETED, "retrieve", {}),
                offset=len(events),
            ),
        }

    async def compose_answer(self, state: AssistantState) -> AssistantState:
        if not state.get("evidence"):
            return {
                "draft_answer": None,
                "draft_error": state.get("draft_error") or "insufficient_evidence",
                "events": self._events(
                    state,
                    (EventType.NODE_STARTED, "compose_answer", {}),
                    (
                        EventType.NODE_COMPLETED,
                        "compose_answer",
                        {"status": "insufficient_evidence"},
                    ),
                ),
            }
        draft, error = await self._generate(
            answer_prompt(
                state["request"].message,
                state["evidence"],
                _history_payload(state),
            )
        )
        return {
            "draft_answer": draft,
            "draft_error": error,
            "events": self._events(
                state,
                (EventType.NODE_STARTED, "compose_answer", {}),
                (
                    EventType.NODE_COMPLETED,
                    "compose_answer",
                    {"structured": draft is not None},
                ),
            ),
        }

    async def validate_answer(self, state: AssistantState) -> AssistantState:
        draft = state.get("draft_answer")
        results: tuple[ValidationResult, ...]
        if draft is None:
            results = (
                ValidationResult(
                    rule="response.structured_output",
                    passed=False,
                    public_message="The response did not match the required structure.",
                ),
            )
        else:
            results = (
                ValidationResult(
                    rule="response.structured_output",
                    passed=True,
                    public_message="The response matches the required structure.",
                ),
                *validate_answer_citations(
                    tuple(claim.evidence_ids for claim in draft.claims),
                    {item.evidence_id for item in state["evidence"]},
                ),
            )
        passed = all(result.passed for result in results)
        return {
            "answer_valid": passed,
            "validations": list(results),
            "events": self._events(
                state,
                (EventType.NODE_STARTED, "validate_answer", {}),
                (
                    EventType.VALIDATION_COMPLETED,
                    "validate_answer",
                    {
                        "passed": passed,
                        "results": [item.model_dump(mode="json") for item in results],
                    },
                ),
                (EventType.NODE_COMPLETED, "validate_answer", {"passed": passed}),
            ),
        }

    async def repair_once(self, state: AssistantState) -> AssistantState:
        failures = tuple(
            result.public_message for result in state.get("validations", []) if not result.passed
        )
        draft, error = await self._generate(
            repair_prompt(
                state["request"].message,
                state["evidence"],
                failures,
                _history_payload(state),
            )
        )
        return {
            "draft_answer": draft,
            "draft_error": error,
            "repair_count": state.get("repair_count", 0) + 1,
            "events": self._events(
                state,
                (EventType.NODE_STARTED, "repair_once", {"attempt": 1}),
                (
                    EventType.NODE_COMPLETED,
                    "repair_once",
                    {"structured": draft is not None},
                ),
            ),
        }

    async def finalize(self, state: AssistantState) -> AssistantState:
        answer = state["draft_answer"]
        assert answer is not None
        specs: list[tuple[EventType, str | None, dict[str, object]]] = [
            (EventType.ANSWER_DELTA, "finalize", {"text": chunk})
            for chunk in _text_chunks(answer.summary)
        ]
        specs.extend(
            [
                (
                    EventType.ANSWER_COMPLETED,
                    "finalize",
                    {
                        "answer": answer.model_dump(mode="json"),
                        "evidence": [item.model_dump(mode="json") for item in state["evidence"]],
                    },
                ),
                (
                    EventType.RUN_COMPLETED,
                    "finalize",
                    {"status": "completed", "incomplete": answer.incomplete},
                ),
            ]
        )
        return {
            "final_answer": answer,
            "events": self._events(state, *specs),
        }

    async def safe_failure(self, state: AssistantState) -> AssistantState:
        answer = GroundedAnswer(claims=(), summary=_SAFE_SUMMARY, incomplete=True)
        specs: list[tuple[EventType, str | None, dict[str, object]]] = [
            (EventType.ANSWER_DELTA, "safe_failure", {"text": chunk})
            for chunk in _text_chunks(answer.summary)
        ]
        specs.extend(
            [
                (
                    EventType.ANSWER_COMPLETED,
                    "safe_failure",
                    {"answer": answer.model_dump(mode="json"), "evidence": []},
                ),
                (
                    EventType.RUN_COMPLETED,
                    "safe_failure",
                    {"status": "insufficient_evidence", "incomplete": True},
                ),
            ]
        )
        return {
            "final_answer": answer,
            "events": self._events(state, *specs),
        }

    async def _generate(self, prompt: str) -> tuple[GroundedAnswer | None, str | None]:
        request = ModelRequest(
            messages=(
                ModelMessage(role=MessageRole.SYSTEM, content=SYSTEM_PROMPT),
                ModelMessage(role=MessageRole.USER, content=prompt),
            ),
            response_schema=cast(dict[str, object], _AnswerDraft.model_json_schema()),
        )
        try:
            result = await self._chat_model.complete(request)
            payload = _extract_json(result.text)
            draft = _AnswerDraft.model_validate(payload)
            return GroundedAnswer.model_validate(draft.model_dump()), None
        except (ValidationError, ValueError, json.JSONDecodeError):
            return None, "invalid_structured_output"
        except Exception:
            return None, "model_unavailable"

    @staticmethod
    def _events(
        state: AssistantState,
        *specs: tuple[EventType, str | None, dict[str, object]],
        offset: int = 0,
    ) -> list[ActivityEvent]:
        start = len(state.get("events", [])) + offset
        request = state["request"]
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


def route_after_compose(state: AssistantState) -> str:
    return "validate_answer" if state.get("evidence") else "safe_failure"


def route_after_validation(state: AssistantState) -> str:
    if state.get("answer_valid"):
        return "finalize"
    if state.get("repair_count", 0) < 1:
        return "repair_once"
    return "safe_failure"


def _extract_json(text: str) -> object:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            stripped = "\n".join(lines[1:-1])
            if stripped.lstrip().startswith("json"):
                stripped = stripped.lstrip()[4:].lstrip()
    return json.loads(stripped)


def _text_chunks(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"\S+\s*", text)) or (text,)


def _retrieval_query(state: AssistantState) -> str:
    prior_questions = [
        message.content for message in state["request"].history if message.role is MessageRole.USER
    ]
    return "\n".join([*prior_questions[-2:], state["request"].message])


def _history_payload(state: AssistantState) -> tuple[dict[str, str], ...]:
    return tuple(
        {"role": message.role.value, "content": message.content}
        for message in state["request"].history[-6:]
    )
