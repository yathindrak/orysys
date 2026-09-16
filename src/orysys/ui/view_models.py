from pydantic import BaseModel, ConfigDict

from orysys.domain.events import ActivityEvent, EventType
from orysys.domain.evidence import Evidence
from orysys.domain.validation import ValidationResult
from orysys.ui.design.icons import Icon


class ActivityItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    warning: bool = False


class EvidenceCard(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    location: str
    excerpt: str
    evidence_id: str
    source: str


class ValidationItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    message: str
    passed: bool


def activity_item(event: ActivityEvent) -> ActivityItem | None:
    if event.type is EventType.NODE_STARTED:
        return ActivityItem(label=f"Running `{event.node or 'workflow'}`")
    if event.type is EventType.RETRIEVAL_COMPLETED:
        count = event.public_payload.get("evidence_count", 0)
        return ActivityItem(label=f"{Icon.RETRIEVAL} Retrieved {count} authorized evidence items")
    if event.type is EventType.VALIDATION_COMPLETED:
        passed = event.public_payload.get("passed") is True
        icon = Icon.VALIDATION if passed else Icon.WARNING
        return ActivityItem(
            label=f"{icon} Validation {'passed' if passed else 'required repair'}",
            warning=not passed,
        )
    if event.type is EventType.RUN_FAILED:
        return ActivityItem(label=f"{Icon.WARNING} The run could not be completed", warning=True)
    return None


def evidence_card(evidence: Evidence) -> EvidenceCard:
    location = evidence.section or "Document"
    if evidence.page is not None:
        location = f"{location} · page {evidence.page}"
    return EvidenceCard(
        title=evidence.title,
        location=location,
        excerpt=evidence.excerpt,
        evidence_id=evidence.evidence_id,
        source=str(evidence.source_uri),
    )


def validation_item(result: ValidationResult) -> ValidationItem:
    return ValidationItem(message=result.public_message, passed=result.passed)
