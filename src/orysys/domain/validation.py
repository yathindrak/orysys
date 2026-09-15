from pydantic import BaseModel, ConfigDict, Field


class ValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule: str = Field(min_length=1)
    passed: bool
    public_message: str = Field(min_length=1, max_length=500)


def validate_citation_ids(
    cited_ids: set[str], authorized_evidence_ids: set[str]
) -> ValidationResult:
    unknown = cited_ids - authorized_evidence_ids
    if unknown:
        return ValidationResult(
            rule="citations.authorized_evidence",
            passed=False,
            public_message="One or more citations do not match authorized evidence.",
        )
    return ValidationResult(
        rule="citations.authorized_evidence",
        passed=True,
        public_message="All citations match authorized evidence.",
    )


def validate_answer_citations(
    claim_citations: tuple[tuple[str, ...], ...], authorized_evidence_ids: set[str]
) -> tuple[ValidationResult, ...]:
    cited_ids = {item for citations in claim_citations for item in citations}
    completeness = ValidationResult(
        rule="citations.claim_completeness",
        passed=bool(claim_citations) and all(claim_citations),
        public_message=(
            "Every claim includes evidence."
            if claim_citations and all(claim_citations)
            else "One or more claims are missing evidence."
        ),
    )
    return (completeness, validate_citation_ids(cited_ids, authorized_evidence_ids))
