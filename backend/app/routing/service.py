"""
Application-level service for route calculations with caching.

Works exclusively through the RoutingProvider abstraction.
"""

from sqlmodel import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.base import RoutingProvider
from app.routing.hashing import compute_request_hash
from app.routing.models import RouteCalculation
from app.routing.repository import RouteCalculationRepository
from app.routing.schemas import CalculateRouteRequest, CalculateRouteResponse

logger = get_logger(__name__)


class RoutingService:
    """Routing service.

    Provides application-level routing operations with caching.
    - Service only knows about RoutingProvider interface
    - Service does NOT import or know about TomTomProvider
    - Provider selection happens via dependency injection
    - Cache/persistence is abstracted through Repository
    """

    def __init__(
        self,
        provider: RoutingProvider,
        session: Session,
    ):
        """Initialize routing service.

        Args:
            provider: RoutingProvider implementation (e.g., TomTomProvider)
            session: Database session for persistence operations
        """
        self.provider = provider
        self.repository = RouteCalculationRepository(session)

    @property
    def provider_name(self) -> str:
        """Name under which results of this provider are cached."""
        name = getattr(self.provider, "provider_name", None)
        return name if isinstance(name, str) else settings.ROUTING_PROVIDER

    async def calculate_route(
        self,
        request: CalculateRouteRequest,
        *,
        force_refresh: bool = False,
    ) -> CalculateRouteResponse:
        """Calculate route with caching.

        This is the main service method that orchestrates route calculation.

        Args:
            request: Route calculation request
            force_refresh: Skip cache and refresh from provider

        Cache logic:
        - If force_refresh=False: try cache first, then provider
        - If force_refresh=True: always call provider, update cache

        Returns:
            Calculated route response

        Raises:
            RoutingError: Various routing errors
        """
        logger.info(
            "Route calculation requested",
            origin=request.route_planning_locations.origin.coordinates,
            destination=request.route_planning_locations.destination.coordinates,
            waypoints_count=(
                len(request.route_planning_locations.waypoints.coordinates)
                if request.route_planning_locations.waypoints
                else 0
            ),
            route_type=request.route_type,
            traffic=request.traffic,
        )

        # Compute request hash for cache lookups
        # A missing vehicle is excluded so hashes of pre-existing cache entries
        # stay valid.
        request_data_dict = request.model_dump(
            mode="json",
            exclude={"vehicle"} if request.vehicle is None else None,
        )
        request_hash = compute_request_hash(request_data_dict)

        # Try cache if not forcing refresh
        if not force_refresh:
            cached = self.repository.get_valid_by_provider_and_hash(
                provider=self.provider_name,
                request_hash=request_hash,
            )

            if cached:
                logger.info(
                    "Route calculation cache hit",
                    request_hash=request_hash,
                    provider=self.provider_name,
                )
                return await self._build_response_from_calculation(cached)

            logger.info(
                "Route calculation cache miss",
                request_hash=request_hash,
                provider=self.provider_name,
            )

        if force_refresh:
            logger.info(
                "Route calculation force refresh",
                request_hash=request_hash,
                provider=self.provider_name,
            )

        # Call provider for fresh result
        logger.info(
            "Calling routing provider",
            provider=self.provider_name,
            request_hash=request_hash,
        )

        response = await self.provider.calculate_route(request)

        # Persist to database
        calculation = await self._persist_calculation(
            request=request,
            response=response,
            request_hash=request_hash,
            request_data_dict=request_data_dict,
        )

        return response.model_copy(update={"id": calculation.id})

    async def _persist_calculation(
        self,
        request: CalculateRouteRequest,
        response: CalculateRouteResponse,
        request_hash: str,
        request_data_dict: dict,
    ) -> RouteCalculation:
        """Persist route calculation to database.

        Args:
            request: Original routing request
            response: Provider response
            request_hash: Computed request hash
            request_data_dict: Serialized request data

        Returns:
            Persisted RouteCalculation entity
        """
        # Extract origin and destination as WKT POINT strings
        # GeoJSONPoint.coordinates is [longitude, latitude]
        origin = request.route_planning_locations.origin
        destination = request.route_planning_locations.destination

        origin_lon, origin_lat = origin.coordinates
        destination_lon, destination_lat = destination.coordinates

        origin_wkt = f"SRID=4326;POINT({origin_lon} {origin_lat})"
        destination_wkt = f"SRID=4326;POINT({destination_lon} {destination_lat})"

        # Extract geometry from response if available.
        # With waypoints a route has one leg per segment, so all legs are
        # concatenated into a single LineString.
        geometry_wkt = None
        if response.routes:
            coords: list[tuple[float, float]] = []
            for leg in response.routes[0].legs or []:
                if leg.path is None:
                    continue
                leg_coords = list(leg.path.coordinates)
                if coords and leg_coords and coords[-1] == leg_coords[0]:
                    leg_coords = leg_coords[1:]
                coords.extend(leg_coords)
            if len(coords) >= 2:
                coords_str = ", ".join(f"{lon} {lat}" for lon, lat in coords)
                geometry_wkt = f"SRID=4326;LINESTRING({coords_str})"

        # Get normalized distance and duration from first route
        distance_meters = 0
        duration_seconds = 0
        if response.routes and len(response.routes) > 0:
            summary = response.routes[0].summary
            distance_meters = summary.length_in_meters
            duration_seconds = summary.travel_duration_in_seconds

        # Prepare provider response (store raw response)
        provider_response = response.model_dump(mode="json")

        # Upsert calculation to database
        calculation = self.repository.upsert_by_provider_and_hash(
            provider=self.provider_name,
            request_hash=request_hash,
            origin_wkt=origin_wkt,
            destination_wkt=destination_wkt,
            distance_meters=distance_meters,
            duration_seconds=duration_seconds,
            request_data=request_data_dict,
            provider_response=provider_response,
            ttl_seconds=settings.ROUTE_CALCULATION_CACHE_TTL_SECONDS,
            geometry_wkt=geometry_wkt,
        )

        logger.info(
            "Route calculation persisted",
            calculation_id=calculation.id,
            request_hash=request_hash,
            provider=self.provider_name,
        )
        return calculation

    async def _build_response_from_calculation(
        self,
        calculation: RouteCalculation,
    ) -> CalculateRouteResponse:
        """Build response from cached calculation.

        Args:
            calculation: Cached RouteCalculation entity

        Returns:
            Reconstructed CalculateRouteResponse

        Notes:
            The provider_response field contains the full response,
            so we deserialize it directly.
        """
        response = CalculateRouteResponse.model_validate(calculation.provider_response)
        return response.model_copy(update={"id": calculation.id})
