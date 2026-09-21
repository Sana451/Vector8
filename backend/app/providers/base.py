"""
Provider protocols.

Domain-oriented interfaces implemented by concrete adapters. A single vendor
may implement several protocols (e.g. TomTom covers routing and traffic), so
interfaces are split by domain rather than by vendor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from app.providers.schemas import (
        FuelStationData,
        LayerQuery,
        RestAreaData,
        RestAreaQuery,
        TrafficLayerData,
        TruckRestrictionData,
    )
    from app.routing.schemas import CalculateRouteRequest, CalculateRouteResponse


@runtime_checkable
class RoutingProvider(Protocol):
    """Calculates routes between locations."""

    async def calculate_route(
        self,
        request: CalculateRouteRequest,
    ) -> CalculateRouteResponse:
        """Calculate a route.

        Args:
            request: Route calculation request.

        Returns:
            Route calculation response with one or more routes.

        Raises:
            ProviderError: If the request fails or no route can be calculated.
        """
        ...


@runtime_checkable
class TrafficProvider(Protocol):
    """Provides live traffic conditions along a corridor."""

    async def get_traffic(self, query: LayerQuery) -> TrafficLayerData:
        """Fetch traffic data along the given path.

        Args:
            query: Corridor query with route geometry and radius.

        Returns:
            Normalized traffic layer payload.

        Raises:
            ProviderError: If the provider call fails.
        """
        ...


@runtime_checkable
class FuelStationProvider(Protocol):
    """Provides fuel stations along a corridor."""

    async def find_stations(self, query: LayerQuery) -> list[FuelStationData]:
        """Find fuel stations along the given path.

        Args:
            query: Corridor query with route geometry and radius.

        Returns:
            List of normalized fuel stations.

        Raises:
            ProviderError: If the provider call fails.
        """
        ...


@runtime_checkable
class TruckRestrictionProvider(Protocol):
    """Provides truck restrictions (bridges, weight limits) along a corridor."""

    async def find_restrictions(self, query: LayerQuery) -> list[TruckRestrictionData]:
        """Find truck restrictions along the given path.

        Args:
            query: Corridor query with route geometry and radius.

        Returns:
            List of normalized truck restrictions.

        Raises:
            ProviderError: If the provider call fails.
        """
        ...


@runtime_checkable
class RestAreaProvider(Protocol):
    """Provides route-adjacent rest areas / truck POI."""

    async def search_along_route(self, query: RestAreaQuery) -> list[RestAreaData]:
        """Search rest areas along the given path.

        Args:
            query: HERE route corridor query with confirmed category ids.

        Returns:
            List of normalized rest areas.

        Raises:
            ProviderError: If the provider call fails.
        """
        ...
