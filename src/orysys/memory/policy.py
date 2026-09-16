import re
from datetime import UTC, datetime, timedelta

from orysys.domain.errors import OrysysError

_SENSITIVE = re.compile(
    r"\b(password|passcode|api[-_ ]?key|access[-_ ]?token|token|bearer|private[-_ ]?key|secret)\b",
    re.IGNORECASE,
)


def validate_memory_content(content: str, expires_at: datetime) -> None:
    if _SENSITIVE.search(content):
        raise OrysysError(
            "memory_sensitive_content",
            "Sensitive credentials cannot be saved as memory.",
        )
    now = datetime.now(UTC)
    if expires_at.utcoffset() is None:
        raise OrysysError(
            "memory_invalid_expiry",
            "Memory expiry must include a timezone.",
        )
    if expires_at <= now or expires_at > now + timedelta(days=365):
        raise OrysysError(
            "memory_invalid_expiry",
            "Memory expiry must be within the next year.",
        )
