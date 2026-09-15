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


class ProviderUnavailable(OrysysError):
    def __init__(self, provider: str) -> None:
        super().__init__(
            "provider_unavailable",
            f"The {provider} service is temporarily unavailable.",
            retryable=True,
        )
