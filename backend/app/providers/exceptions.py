"""
Generic provider exceptions.

Shared exception hierarchy for all external data providers
(routing, traffic, fuel stations, truck restrictions).

Domain-specific modules may subclass these to keep their own
``except`` semantics while remaining catchable as ``ProviderError``.
"""


class ProviderError(Exception):
    """Base exception for all provider errors."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        provider_code: str | None = None,
        status_code: int | None = None,
    ):
        """Initialize provider error.

        Args:
            message: Error message.
            provider: Provider name (e.g., 'tomtom').
            provider_code: Provider-specific error code.
            status_code: HTTP status code.
        """
        self.message = message
        self.provider = provider
        self.provider_code = provider_code
        self.status_code = status_code
        super().__init__(message)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"provider={self.provider!r}, "
            f"provider_code={self.provider_code!r}, "
            f"status_code={self.status_code!r})"
        )


class ProviderRequestError(ProviderError):
    """Generic provider failure (unexpected status or transport error)."""


class ProviderBadRequestError(ProviderError):
    """Bad request error (400)."""


class ProviderAuthenticationError(ProviderError):
    """Authentication error (401/403)."""


class ProviderRateLimitError(ProviderError):
    """Rate limit exceeded (429)."""


class ProviderTimeoutError(ProviderError):
    """Request timeout."""


class ProviderUnavailableError(ProviderError):
    """Provider temporarily unavailable or not configured."""


class ProviderNotRegisteredError(ProviderError):
    """Requested provider is not present in the registry."""
