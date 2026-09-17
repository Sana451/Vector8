"""
Routing provider abstraction.

Base interface for routing providers.
"""

from abc import ABC, abstractmethod

from app.routing.schemas import CalculateRouteRequest, CalculateRouteResponse


class RoutingProvider(ABC):
    """Abstract base class for routing providers.

    Defines the interface that all routing providers must implement.
    Providers handle the actual HTTP communication with external routing APIs
    and translate between application schemas and provider-specific formats.
    """

    @abstractmethod
    async def calculate_route(
        self,
        request: CalculateRouteRequest,
    ) -> CalculateRouteResponse:
        """Calculate route for given request.

        Args:
            request: Route calculation request with locations, options, and vehicle
            params

        Returns:
            Route calculation response with one or more routes

        Raises:
            RoutingError: If the request fails or no route can be calculated
        """
        ...
