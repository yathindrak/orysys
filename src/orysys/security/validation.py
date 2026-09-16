import re
from urllib.parse import urlparse

from orysys.domain.errors import OrysysError

_DISALLOWED_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_EXFILTRATION = re.compile(
    r"\b(?:reveal|print|return|send|exfiltrate)\b.{0,40}\b"
    r"(?:api key|access token|password|system prompt|private key)\b",
    re.IGNORECASE | re.DOTALL,
)


def validate_user_message(message: str) -> None:
    if _DISALLOWED_CONTROL.search(message):
        raise OrysysError(
            "invalid_request_content", "The request contains unsupported control characters."
        )
    if _EXFILTRATION.search(message):
        raise OrysysError(
            "unsafe_request",
            "Requests for credentials or hidden system instructions are not permitted.",
        )


def validate_outbound_url(url: str, allowed_hosts: frozenset[str]) -> None:
    parsed = urlparse(url)
    if not parsed.hostname or (
        parsed.scheme != "https"
        and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"})
    ):
        raise ValueError("outbound URL must use HTTPS except on loopback")
    if parsed.username or parsed.password or parsed.hostname not in allowed_hosts:
        raise ValueError("outbound URL host is not allow-listed")
