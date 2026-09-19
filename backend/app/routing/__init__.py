"""
Routing module.
Provides route calculation on top of the shared provider layer.
Architecture:
- router.py: HTTP API endpoints
- service.py: Business logic (provider-agnostic)
- schemas.py: Pydantic request/response models
- exceptions.py: Routing-specific exceptions
- dependencies.py: Dependency injection
Provider adapters live in :mod:`app.providers`.
"""

from typing import Any

from app.routing.schemas import (
    CalculateRouteRequest,
    CalculateRouteResponse,
    RoutePlanningLocations,
)

__all__ = [
    "router",
    "CalculateRouteRequest",
    "CalculateRouteResponse",
    "RoutePlanningLocations",
]


def __getattr__(name: str) -> Any:
    """Lazily expose the APIRouter to keep module import side effects minimal."""
    if name == "router":
        from app.routing.router import router

        return router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
