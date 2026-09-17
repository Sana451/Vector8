"""
Routing module dependencies.

Dependency injection and provider factory functions.
"""

from typing import Annotated

from fastapi import Depends

from app.core.config import settings
from app.routing.providers.base import RoutingProvider
from app.routing.providers.tomtom import TomTomProvider
from app.routing.service import RoutingService


def get_routing_provider() -> RoutingProvider:
    """Factory function to get configured routing provider.

    Provider selection is based on ROUTING_PROVIDER setting.
    Currently supports: tomtom

    Returns:
        Configured RoutingProvider instance

    Raises:
        ValueError: If provider is not supported
    """
    if settings.ROUTING_PROVIDER == "tomtom":
        return TomTomProvider()
    else:
        raise ValueError(
            f"Unsupported routing provider: {settings.ROUTING_PROVIDER}. "
            f"Supported: tomtom"
        )


def get_routing_service(
    provider: RoutingProvider = Depends(get_routing_provider),
) -> RoutingService:
    """Factory function to get routing service.

    Args:
        provider: RoutingProvider instance (injected)

    Returns:
        RoutingService instance
    """
    return RoutingService(provider=provider)


# Annotated type for dependency injection in route handlers
RoutingServiceDep = Annotated[RoutingService, Depends(get_routing_service)]
