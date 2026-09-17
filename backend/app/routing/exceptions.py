"""
Routing module exceptions.

Custom exceptions for routing provider errors with support for provider-specific
error codes and context preservation.
"""


class RoutingError(Exception):
    """Base exception for routing module."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        provider_code: str | None = None,
        status_code: int | None = None,
    ):
        """Initialize routing error.

        Args:
            message: Error message
            provider: Provider name (e.g., 'tomtom')
            provider_code: Provider-specific error code
            status_code: HTTP status code
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


class RoutingProviderError(RoutingError):
    """Generic provider error (500, 502, 503, 504)."""

    pass


class RoutingBadRequestError(RoutingError):
    """Bad request error (400)."""

    pass


class RoutingAuthenticationError(RoutingError):
    """Authentication error (403)."""

    pass


class RoutingRateLimitError(RoutingError):
    """Rate limit exceeded (429)."""

    pass


class RoutingTimeoutError(RoutingError):
    """Request timeout."""

    pass


class RoutingUnavailableError(RoutingError):
    """Provider temporarily unavailable."""

    pass


class RoutingNoRouteFoundError(RoutingError):
    """No route found for given parameters."""

    pass


class RoutingMapMatchingError(RoutingError):
    """Map matching failure."""

    pass


# Provider-specific error code mappings
PROVIDER_ERROR_MAPPING = {
    "NO_ROUTE_FOUND": RoutingNoRouteFoundError,
    "MAP_MATCHING_FAILURE": RoutingMapMatchingError,
    "CANNOT_RESTORE_BASEROUTE": RoutingProviderError,
    "BAD_INPUT": RoutingBadRequestError,
    "COMPUTE_TIME_LIMIT_EXCEEDED": RoutingProviderError,
}
