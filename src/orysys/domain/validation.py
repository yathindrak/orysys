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
