import re
from collections.abc import Mapping
from typing import Any

import structlog

_SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "answer",
        "api_key",
        "api_token",
        "client_secret",
        "content",
        "document_body",
        "excerpt",
        "message",
        "password",
        "prompt",
        "query",
        "secret",
        "summary",
        "text",
        "token",
    }
)
_BEARER_PATTERN = re.compile(r"(?i)bearer\s+[a-z0-9._~+/-]+")


def redact(value: Any) -> Any:
    """Return telemetry-safe data without credentials or document bodies."""

    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if _is_sensitive(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _BEARER_PATTERN.sub("Bearer [REDACTED]", value)
    return value


def _is_sensitive(key: str) -> bool:
    normalized = key.casefold()
    return any(part in normalized for part in _SENSITIVE_KEYS)


def configure_logging(level: str) -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
    )


def get_logger() -> Any:
    return structlog.get_logger()
