import operator
from typing import Annotated, Literal, TypedDict

from orysys.application.assistant import AssistantRequest
from orysys.domain.events import ActivityEvent
from orysys.domain.evidence import Evidence, GroundedAnswer
from orysys.domain.identity import AccessScope, Principal
from orysys.domain.validation import ValidationResult


class AssistantState(TypedDict, total=False):
    request: AssistantRequest
    principal: Principal
    run_id: str
    route: Literal["direct_retrieval"]
    access_scope: AccessScope
    evidence: tuple[Evidence, ...]
    draft_answer: GroundedAnswer | None
    final_answer: GroundedAnswer
    draft_error: str | None
    answer_valid: bool
    repair_count: int
    validations: Annotated[list[ValidationResult], operator.add]
    events: Annotated[list[ActivityEvent], operator.add]
