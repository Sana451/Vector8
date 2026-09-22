"""
Map layer services.

One service per domain. Each service calls its provider, persists the result
with a domain-specific TTL and falls back to cached PostGIS rows when the
provider is unavailable.
"""

from sqlmodel import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.map.models import FuelStation, MapRestAreasCache, TruckRestriction
from app.map.repository import (
    FuelStationRepository,
    RestAreaCacheRepository,
    TrafficSnapshotRepository,
    TruckRestrictionRepository,
    build_rest_area_row,
)
from app.providers.base import (
    FuelStationProvider,
    RestAreaProvider,
    TrafficProvider,
    TruckRestrictionProvider,
)
from app.providers.exceptions import ProviderError
from app.providers.geo import GeoJSONPoint, point_to_wkt
from app.providers.here.poi import (
    HERE_BROWSE_MAX_LIMIT,
    HERE_EXCURSION_DISTANCE_RANKING,
    HERE_REST_AREA_CATEGORY_IDS,
)
from app.providers.schemas import (
    FuelStationData,
    LayerQuery,
    RestAreaData,
    RestAreaQuery,
    RestrictionType,
    TrafficLayerData,
    TruckRestrictionData,
)
from app.routing.hashing import compute_request_hash

logger = get_logger(__name__)


def _corridor_hash(provider: str, query: LayerQuery) -> str:
    """Compute a deterministic cache key for a corridor query."""
    return compute_request_hash(
        {
            "provider": provider,
            "radius_meters": query.radius_meters,
            "limit": query.limit,
            "coordinates": [list(coord) for coord in query.coordinates],
        }
    )


def _route_hash(coordinates: list[tuple[float, float]]) -> str:
    """Hash a route geometry independent of the layer provider."""
    return compute_request_hash(
        {
            "coordinates": [list(coord) for coord in coordinates],
        }
    )


def _rest_area_request_hash(
    provider: str, query: RestAreaQuery
) -> tuple[str, str, str]:
    """Compute the route hash and cache key for HERE rest area queries."""
    route_hash = _route_hash(query.coordinates)
    categories_hash = compute_request_hash(
        {
            "categories": sorted(query.categories),
        }
    )
    request_hash = compute_request_hash(
        {
            "provider": provider,
            "route_hash": route_hash,
            "categories": sorted(query.categories),
            "corridor_width_meters": query.corridor_width_meters,
            "limit": query.limit,
            "ranking": query.ranking,
        }
    )
    return route_hash, categories_hash, request_hash


class TrafficService:
    """Traffic layer service with snapshot caching."""

    def __init__(self, provider: TrafficProvider, session: Session):
        """Initialize traffic service.

        Args:
            provider: Configured traffic provider.
            session: Database session.
        """
        self.provider = provider
        self.provider_name = settings.TRAFFIC_PROVIDER
        self.repository = TrafficSnapshotRepository(session)

    async def get_traffic(
        self,
        query: LayerQuery,
        *,
        force_refresh: bool = False,
    ) -> TrafficLayerData:
        """Get traffic data for the corridor.

        Args:
            query: Corridor query.
            force_refresh: Skip cache and call the provider.

        Returns:
            Traffic layer payload.

        Raises:
            ProviderError: If the provider fails and no cache is available.
        """
        request_hash = _corridor_hash(self.provider_name, query)

        if not force_refresh:
            cached = self.repository.get_valid(self.provider_name, request_hash)
            if cached is not None:
                logger.info("Traffic cache hit", request_hash=request_hash)
                return TrafficLayerData.model_validate(cached.payload)

        try:
            data = await self.provider.get_traffic(query)
        except ProviderError as exc:
            stale = self.repository.get_valid(self.provider_name, request_hash)
            if stale is not None:
                logger.warning(
                    "Traffic provider failed, serving cache",
                    provider=self.provider_name,
                    error=exc.message,
                )
                return TrafficLayerData.model_validate(stale.payload)
            raise

        self.repository.upsert(
            provider=self.provider_name,
            request_hash=request_hash,
            payload=data.model_dump(mode="json"),
            ttl_seconds=settings.TRAFFIC_CACHE_TTL_SECONDS,
            coordinates=query.coordinates,
        )

        return data


class FuelService:
    """Fuel station layer service backed by PostGIS."""

    def __init__(self, provider: FuelStationProvider, session: Session):
        """Initialize fuel service.

        Args:
            provider: Configured fuel station provider.
            session: Database session.
        """
        self.provider = provider
        self.provider_name = settings.FUEL_PROVIDER
        self.repository = FuelStationRepository(session)

    async def find_stations(
        self,
        query: LayerQuery,
        *,
        force_refresh: bool = False,
    ) -> list[FuelStationData]:
        """Find fuel stations along the corridor.

        Args:
            query: Corridor query.
            force_refresh: Skip cache and call the provider.

        Returns:
            List of fuel stations.

        Raises:
            ProviderError: If the provider fails and no cached rows exist.
        """
        if not force_refresh:
            cached = self._from_cache(query)
            if cached:
                logger.info("Fuel cache hit", count=len(cached))
                return cached

        try:
            stations = await self.provider.find_stations(query)
        except ProviderError as exc:
            cached = self._from_cache(query)
            if cached:
                logger.warning(
                    "Fuel provider failed, serving cache",
                    provider=self.provider_name,
                    error=exc.message,
                )
                return cached
            raise

        self.repository.upsert_many(
            provider=self.provider_name,
            stations=[self._to_row(station) for station in stations],
            ttl_seconds=settings.FUEL_CACHE_TTL_SECONDS,
        )

        return stations

    def _from_cache(self, query: LayerQuery) -> list[FuelStationData]:
        """Read fresh rows from PostGIS along the corridor."""
        rows = self.repository.find_along_route(
            coordinates=query.coordinates,
            radius_meters=query.radius_meters,
            limit=query.limit,
            provider=self.provider_name,
        )
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _to_row(station: FuelStationData) -> dict:
        """Map a provider DTO onto repository row values."""
        lon, lat = station.location.coordinates
        return {
            "external_id": station.external_id,
            "name": station.name,
            "brand": station.brand,
            "address": station.address,
            "location": point_to_wkt(lon, lat),
            "diesel_price": station.diesel_price,
            "medium_truck_accessible": station.medium_truck_accessible,
            "large_truck_accessible": station.large_truck_accessible,
            "payload": station.model_dump(mode="json"),
        }

    @staticmethod
    def _from_row(row: FuelStation) -> FuelStationData:
        """Rebuild a provider DTO from a cached row."""
        return FuelStationData.model_validate(row.payload)


class TruckRestrictionService:
    """Truck restriction layer service backed by PostGIS."""

    def __init__(self, provider: TruckRestrictionProvider, session: Session):
        """Initialize truck restriction service.

        Args:
            provider: Configured truck restriction provider.
            session: Database session.
        """
        self.provider = provider
        self.provider_name = settings.TRUCK_RESTRICTION_PROVIDER
        self.repository = TruckRestrictionRepository(session)

    async def find_restrictions(
        self,
        query: LayerQuery,
        *,
        force_refresh: bool = False,
    ) -> list[TruckRestrictionData]:
        """Find truck restrictions along the corridor.

        Args:
            query: Corridor query.
            force_refresh: Skip cache and call the provider.

        Returns:
            List of truck restrictions.

        Raises:
            ProviderError: If the provider fails and no cached rows exist.
        """
        if not force_refresh:
            cached = self._from_cache(query)
            if cached:
                logger.info("Truck restriction cache hit", count=len(cached))
                return cached

        try:
            restrictions = await self.provider.find_restrictions(query)
        except ProviderError as exc:
            cached = self._from_cache(query)
            if cached:
                logger.warning(
                    "Truck restriction provider failed, serving cache",
                    provider=self.provider_name,
                    error=exc.message,
                )
                return cached
            raise

        self.repository.upsert_many(
            provider=self.provider_name,
            restrictions=[self._to_row(item) for item in restrictions],
            ttl_seconds=settings.TRUCK_RESTRICTION_CACHE_TTL_SECONDS,
        )

        return restrictions

    def _from_cache(self, query: LayerQuery) -> list[TruckRestrictionData]:
        """Read fresh rows from PostGIS along the corridor."""
        rows = self.repository.find_along_route(
            coordinates=query.coordinates,
            radius_meters=query.radius_meters,
            limit=query.limit,
            provider=self.provider_name,
        )
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _to_row(restriction: TruckRestrictionData) -> dict:
        """Map a provider DTO onto repository row values."""
        lon, lat = restriction.location.coordinates
        return {
            "external_id": restriction.external_id,
            "restriction_type": restriction.restriction_type.value,
            "description": restriction.description,
            "location": point_to_wkt(lon, lat),
            "max_height_cm": restriction.max_height_cm,
            "max_weight_kg": restriction.max_weight_kg,
            "max_width_cm": restriction.max_width_cm,
            "max_length_cm": restriction.max_length_cm,
            "payload": restriction.model_dump(mode="json"),
        }

    @staticmethod
    def _from_row(row: TruckRestriction) -> TruckRestrictionData:
        """Rebuild a provider DTO from a cached row."""
        payload = row.payload
        if payload:
            return TruckRestrictionData.model_validate(payload)

        return TruckRestrictionData(
            external_id=row.external_id,
            restriction_type=RestrictionType(row.restriction_type),
            description=row.description,
            location=GeoJSONPoint(coordinates=(0.0, 0.0)),
        )


class HerePoiService:
    """Rest area layer service backed by route-specific cache rows."""

    def __init__(self, provider: RestAreaProvider, session: Session):
        self.provider = provider
        self.provider_name = settings.REST_AREAS_PROVIDER
        self.repository = RestAreaCacheRepository(session)

    async def find_rest_areas(
        self,
        query: LayerQuery,
        *,
        force_refresh: bool = False,
    ) -> list[RestAreaData]:
        """Find confirmed HERE rest areas along the route corridor."""
        provider_query = RestAreaQuery(
            path=query.path,
            categories=list(HERE_REST_AREA_CATEGORY_IDS),
            corridor_width_meters=settings.HERE_POI_CORRIDOR_WIDTH_METERS,
            limit=min(query.limit, settings.HERE_POI_LIMIT, HERE_BROWSE_MAX_LIMIT),
            ranking=(
                HERE_EXCURSION_DISTANCE_RANKING
                if settings.HERE_POI_USE_EXCURSION_DISTANCE_RANKING
                else None
            ),
        )
        route_hash, categories_hash, request_hash = _rest_area_request_hash(
            self.provider_name,
            provider_query,
        )

        logger.info(
            "HERE rest area lookup started",
            provider=self.provider_name,
            request_hash=request_hash,
            route_hash=route_hash,
            categories_hash=categories_hash,
            force_refresh=force_refresh,
            requested_limit=query.limit,
            effective_limit=provider_query.limit,
            categories=provider_query.categories,
            corridor_width_meters=provider_query.corridor_width_meters,
            ranking=provider_query.ranking,
        )

        if not force_refresh:
            cached = self._from_cache(request_hash)
            if cached:
                logger.info(
                    "HERE rest area cache hit",
                    provider=self.provider_name,
                    request_hash=request_hash,
                    route_hash=route_hash,
                    count=len(cached),
                )
                return cached
            logger.info(
                "HERE rest area cache miss",
                provider=self.provider_name,
                request_hash=request_hash,
                route_hash=route_hash,
            )

        logger.info(
            "HERE rest area provider request",
            provider=self.provider_name,
            request_hash=request_hash,
            categories=provider_query.categories,
        )

        try:
            rest_areas = await self.provider.search_along_route(provider_query)
        except ProviderError as exc:
            cached = self._from_cache(request_hash)
            if cached:
                logger.warning(
                    "HERE rest area provider failed, serving cache",
                    provider=self.provider_name,
                    request_hash=request_hash,
                    route_hash=route_hash,
                    count=len(cached),
                    error=exc.message,
                )
                return cached
            raise

        logger.info(
            "HERE rest area provider response",
            provider=self.provider_name,
            request_hash=request_hash,
            route_hash=route_hash,
            count=len(rest_areas),
        )

        self.repository.replace_many(
            provider=self.provider_name,
            request_hash=request_hash,
            route_hash=route_hash,
            categories_hash=categories_hash,
            corridor_width_meters=provider_query.corridor_width_meters,
            rows=[self._to_row(rest_area) for rest_area in rest_areas],
            ttl_seconds=settings.HERE_POI_CACHE_TTL_SECONDS,
        )

        logger.info(
            "HERE rest area cache updated",
            provider=self.provider_name,
            request_hash=request_hash,
            route_hash=route_hash,
            count=len(rest_areas),
            ttl_seconds=settings.HERE_POI_CACHE_TTL_SECONDS,
        )

        return rest_areas

    def _from_cache(self, request_hash: str) -> list[RestAreaData]:
        rows = self.repository.get_valid(self.provider_name, request_hash)
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _to_row(rest_area: RestAreaData) -> dict:
        lon, lat = rest_area.position.coordinates
        return build_rest_area_row(
            provider_place_id=rest_area.provider_place_id,
            title=rest_area.title,
            longitude=lon,
            latitude=lat,
            payload=rest_area.model_dump(mode="json"),
            access=[point.model_dump(mode="json") for point in rest_area.access_points],
            address=(
                rest_area.address.model_dump(mode="json")
                if rest_area.address is not None
                else None
            ),
            categories=[item.model_dump(mode="json") for item in rest_area.categories],
            distance_meters=rest_area.distance_meters,
            result_type=rest_area.result_type,
            ontology_id=rest_area.ontology_id,
            opening_hours=rest_area.opening_hours,
            contacts=rest_area.contacts,
            chains=[item.model_dump(mode="json") for item in rest_area.chains],
            references=[item.model_dump(mode="json") for item in rest_area.references],
            metadata_payload=rest_area.metadata,
        )

    @staticmethod
    def _from_row(row: MapRestAreasCache) -> RestAreaData:
        return RestAreaData.model_validate(row.payload)
