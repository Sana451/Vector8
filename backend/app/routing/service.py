"""
Routing business logic service.

Application-level service for route calculations.
Works exclusively through the RoutingProvider abstraction.
"""

import logging

from app.routing.providers.base import RoutingProvider
from app.routing.schemas import CalculateRouteRequest, CalculateRouteResponse

logger = logging.getLogger(__name__)


class RoutingService:
    """Routing service.

    Provides application-level routing operations.
    Delegates actual routing calculations to configured provider.

    Design principle:
    - Service only knows about RoutingProvider interface
    - Service does NOT import or know about TomTomProvider
    - Provider selection happens via dependency injection
    """

    def __init__(self, provider: RoutingProvider):
        """Initialize routing service.

        Args:
            provider: RoutingProvider implementation (e.g., TomTomProvider)
        """
        self.provider = provider

    async def calculate_route(
        self,
        request: CalculateRouteRequest,
    ) -> CalculateRouteResponse:
        """Calculate route.

        This is the main service method that orchestrates route calculation.
        It delegates to the configured provider without knowing provider details.

        Args:
            request: Route calculation request

        Returns:
            Calculated route response

        Raises:
            RoutingError: Various routing errors
        """
        logger.info(
            "Route calculation requested",
            extra={
                "origin": request.route_planning_locations.origin.coordinates,
                "destination": (
                    request.route_planning_locations.destination.coordinates
                ),
                "waypoints_count": (
                    len(request.route_planning_locations.waypoints.coordinates)
                    if request.route_planning_locations.waypoints
                    else 0
                ),
                "route_type": request.route_type,
                "traffic": request.traffic,
            },
        )

        return await self.provider.calculate_route(request)
