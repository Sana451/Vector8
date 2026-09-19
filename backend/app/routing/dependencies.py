"""
Routing module dependencies.

Dependency injection and provider factory functions.
"""

from typing import Annotated

from fastapi import Depends

from app.api.deps import SessionDep
from app.core.config import settings
from app.providers.base import RoutingProvider
from app.providers.registry import registry
from app.routing.service import RoutingService


def get_routing_provider() -> RoutingProvider:
    """Factory function to get configured routing provider.

    Provider selection is based on the ROUTING_PROVIDER setting and resolved
    through the shared provider registry.

    Returns:
        Configured RoutingProvider instance

    Raises:
        ProviderNotRegisteredError: If the provider is not registered
    """
    return registry.get("routing", settings.ROUTING_PROVIDER)


def get_routing_service(
    session: SessionDep,
    provider: RoutingProvider = Depends(get_routing_provider),
) -> RoutingService:
    """Factory function to get routing service.

    Args:
        session: Database session (injected)
        provider: RoutingProvider instance (injected)

    Returns:
        RoutingService instance with cache support
    """
    return RoutingService(provider=provider, session=session)


# Annotated type for dependency injection in route handlers
RoutingServiceDep = Annotated[RoutingService, Depends(get_routing_service)]
