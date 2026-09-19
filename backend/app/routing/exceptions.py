"""
Routing module exceptions.

Routing-specific exceptions built on top of the shared provider hierarchy in
:mod:`app.providers.exceptions`.

Every ``Routing*Error`` is both a ``RoutingError`` (preserving existing
``except`` clauses) and the matching generic ``Provider*Error``, so the map
orchestrator can treat all layers uniformly.
"""

from app.providers.exceptions import (
    ProviderAuthenticationError,
    ProviderBadRequestError,
    ProviderError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


class RoutingError(ProviderError):
    """Base exception for routing module."""

    pass


class RoutingProviderError(RoutingError, ProviderRequestError):
    """Generic provider error (500, 502, 503, 504)."""

    pass


class RoutingBadRequestError(RoutingError, ProviderBadRequestError):
    """Bad request error (400)."""

    pass


class RoutingAuthenticationError(RoutingError, ProviderAuthenticationError):
    """Authentication error (403)."""

    pass


class RoutingRateLimitError(RoutingError, ProviderRateLimitError):
    """Rate limit exceeded (429)."""

    pass


class RoutingTimeoutError(RoutingError, ProviderTimeoutError):
    """Request timeout."""

    pass


class RoutingUnavailableError(RoutingError, ProviderUnavailableError):
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
