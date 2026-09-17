"""
Routing module.

Provides routing functionality with pluggable provider architecture.

Architecture:
- router.py: HTTP API endpoints
- service.py: Business logic (provider-agnostic)
- providers/: Provider implementations (TomTom, etc.)
- schemas.py: Pydantic request/response models
- exceptions.py: Routing-specific exceptions
- dependencies.py: Dependency injection
"""

from app.routing.router import router
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
