"""
Map layer orchestrator.

Resolves every requested layer concurrently and merges the results into a
single response. Optional layers degrade gracefully: their failure is recorded
in ``errors`` instead of aborting the request. The route layer is mandatory -
its failure propagates to the caller.
"""

import asyncio

from app.core.config import settings
from app.core.logging import get_logger
from app.geocoding.service import GeocodingService
from app.map.schemas import (
    LayerError,
    MapLayer,
    MapOverviewRequest,
    MapOverviewResponse,
    RouteLayerData,
)
from app.map.services import FuelService, TrafficService, TruckRestrictionService
from app.providers.exceptions import ProviderError
from app.providers.geo import GeoJSONLineString
from app.providers.schemas import (
    FuelStationData,
    LayerQuery,
    TrafficLayerData,
    TruckRestrictionData,
)
from app.routing.schemas import (
    CalculateRouteRequest,
    CalculateRouteResponse,
    RoutePlanningLocations,
)
from app.routing.service import RoutingService

logger = get_logger(__name__)


class MapLayerService:
    """Aggregates map layers into a single overview response."""

    def __init__(
        self,
        geocoding_service: GeocodingService,
        routing_service: RoutingService,
        traffic_service: TrafficService,
        fuel_service: FuelService,
        truck_restriction_service: TruckRestrictionService,
    ):
        """Initialize the orchestrator.

        Args:
            geocoding_service: Address normalization service.
            routing_service: Route layer service.
            traffic_service: Traffic layer service.
            fuel_service: Fuel layer service.
            truck_restriction_service: Truck restriction layer service.
        """
        self.geocoding_service = geocoding_service
        self.routing_service = routing_service
        self.traffic_service = traffic_service
        self.fuel_service = fuel_service
        self.truck_restriction_service = truck_restriction_service

    async def get_overview(
        self,
        request: MapOverviewRequest,
        *,
        force_refresh: bool = False,
    ) -> MapOverviewResponse:
        """Build an aggregated map overview.

        The route is resolved first because its geometry is the corridor used by
        every other layer. Remaining layers run concurrently.

        Args:
            request: Aggregated map request.
            force_refresh: Skip caches and refresh from providers.

        Returns:
            Aggregated response with per-layer errors.

        Raises:
            ProviderError: If the mandatory route layer fails.
        """
        requested = set(request.layers or list(MapLayer))
        errors: list[LayerError] = []

        route_request = await self._build_route_request(
            request,
            force_refresh=force_refresh,
        )

        route_response = await self.routing_service.calculate_route(
            request=route_request,
            force_refresh=force_refresh,
        )
        route_layer = RouteLayerData(
            provider=settings.ROUTING_PROVIDER,
            routes=route_response.routes,
        )

        path = self._extract_path(route_response)
        if path is None:
            logger.warning("Route has no usable geometry, skipping point layers")
            return MapOverviewResponse(route=route_layer, errors=errors)

        query = LayerQuery(
            path=path,
            radius_meters=request.radius_meters or settings.MAP_LAYER_RADIUS_METERS,
            limit=request.limit or settings.MAP_LAYER_RESULT_LIMIT,
        )

        tasks: dict[MapLayer, asyncio.Future] = {}

        if MapLayer.TRAFFIC in requested:
            tasks[MapLayer.TRAFFIC] = asyncio.ensure_future(
                self.traffic_service.get_traffic(query, force_refresh=force_refresh)
            )
        if MapLayer.FUEL in requested:
            tasks[MapLayer.FUEL] = asyncio.ensure_future(
                self.fuel_service.find_stations(query, force_refresh=force_refresh)
            )
        if MapLayer.TRUCK_RESTRICTIONS in requested:
            tasks[MapLayer.TRUCK_RESTRICTIONS] = asyncio.ensure_future(
                self.truck_restriction_service.find_restrictions(
                    query, force_refresh=force_refresh
                )
            )

        if not tasks:
            return MapOverviewResponse(route=route_layer, errors=errors)

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        traffic: TrafficLayerData | None = None
        fuel_stations: list[FuelStationData] = []
        truck_restrictions: list[TruckRestrictionData] = []

        for layer, result in zip(tasks.keys(), results, strict=True):
            if isinstance(result, BaseException):
                errors.append(self._to_layer_error(layer, result))
                continue

            if layer is MapLayer.TRAFFIC:
                traffic = result
            elif layer is MapLayer.FUEL:
                fuel_stations = result
            elif layer is MapLayer.TRUCK_RESTRICTIONS:
                truck_restrictions = result

        return MapOverviewResponse(
            route=route_layer,
            traffic=traffic,
            fuel_stations=fuel_stations,
            truck_restrictions=truck_restrictions,
            errors=errors,
        )

    async def _build_route_request(
        self,
        request: MapOverviewRequest,
        *,
        force_refresh: bool,
    ) -> CalculateRouteRequest:
        """Normalize map request into the canonical routing request."""
        if request.route is not None:
            return request.route

        assert request.pickup is not None
        assert request.delivery is not None

        pickup, delivery = await asyncio.gather(
            self.geocoding_service.normalize_point(
                request.pickup,
                force_refresh=force_refresh,
            ),
            self.geocoding_service.normalize_point(
                request.delivery,
                force_refresh=force_refresh,
            ),
        )

        return CalculateRouteRequest(
            route_planning_locations=RoutePlanningLocations(
                origin=pickup,
                destination=delivery,
            )
        )

    @staticmethod
    def _extract_path(response: CalculateRouteResponse) -> GeoJSONLineString | None:
        """Extract the corridor geometry from a route response.

        Concatenates the geometry of every leg of the first route.

        Args:
            response: Route calculation response.

        Returns:
            LineString covering the route, or None when unavailable.
        """
        if not response.routes:
            return None

        coordinates: list[tuple[float, float]] = []
        for leg in response.routes[0].legs or []:
            if leg.path:
                coordinates.extend(leg.path.coordinates)

        if len(coordinates) < 2:
            return None

        return GeoJSONLineString(coordinates=coordinates)

    @staticmethod
    def _to_layer_error(layer: MapLayer, error: BaseException) -> LayerError:
        """Convert a layer exception into a non-fatal error entry."""
        if isinstance(error, ProviderError):
            logger.warning(
                "Map layer failed",
                layer=layer.value,
                provider=error.provider,
                error=error.message,
            )
            return LayerError(
                layer=layer,
                provider=error.provider,
                message=error.message,
            )

        logger.error(
            "Map layer raised unexpected error",
            layer=layer.value,
            error=str(error),
            error_type=type(error).__name__,
        )
        return LayerError(layer=layer, message=str(error) or "Unexpected layer error")
