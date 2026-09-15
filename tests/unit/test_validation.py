from orysys.domain.validation import validate_citation_ids


def test_citation_validation_accepts_only_authorized_evidence() -> None:
    result = validate_citation_ids({"ev-1"}, {"ev-1", "ev-2"})
    assert result.passed


def test_citation_validation_rejects_unknown_ids_without_exposing_them() -> None:
    result = validate_citation_ids({"ev-secret"}, {"ev-1"})
    assert not result.passed
    assert "ev-secret" not in result.public_message
