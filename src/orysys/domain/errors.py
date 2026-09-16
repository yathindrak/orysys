class OrysysError(Exception):
    """Base error carrying a stable public code without sensitive provider detail."""

    def __init__(self, code: str, public_message: str, *, retryable: bool = False) -> None:
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
        self.retryable = retryable


class AuthorizationDenied(OrysysError):
    def __init__(self) -> None:
        super().__init__("authorization_denied", "This action is not permitted.")


class AuthenticationFailed(OrysysError):
    def __init__(self) -> None:
        super().__init__("authentication_failed", "A valid access token is required.")


class AuthenticationUnavailable(OrysysError):
    def __init__(self) -> None:
        super().__init__(
            "authentication_unavailable",
            "Authentication is temporarily unavailable.",
            retryable=True,
        )


class RateLimitExceeded(OrysysError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("rate_limit_exceeded", "Too many requests. Please retry later.")
        self.retry_after_seconds = max(1, retry_after_seconds)


class RateLimitUnavailable(OrysysError):
    def __init__(self) -> None:
        super().__init__(
            "rate_limit_unavailable",
            "Request limiting is temporarily unavailable.",
            retryable=True,
        )


class ProviderUnavailable(OrysysError):
    def __init__(self, provider: str) -> None:
        super().__init__(
            "provider_unavailable",
            f"The {provider} service is temporarily unavailable.",
            retryable=True,
        )


class ResourceNotFound(OrysysError):
    def __init__(self, resource: str) -> None:
        super().__init__("resource_not_found", f"The requested {resource} was not found.")
