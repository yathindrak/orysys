from orysys.observability import redact


def test_redaction_removes_secrets_and_document_content_recursively() -> None:
    value = {
        "api_token": "secret-value",
        "nested": {"excerpt": "restricted text"},
        "public_payload": {"text": "generated answer token"},
        "header": "Bearer abc.def",
        "safe": "kept",
    }

    redacted = redact(value)

    assert redacted == {
        "api_token": "[REDACTED]",
        "nested": {"excerpt": "[REDACTED]"},
        "public_payload": {"text": "[REDACTED]"},
        "header": "Bearer [REDACTED]",
        "safe": "kept",
    }
