"""
Map layer services.

One service per domain. Each service calls its provider, persists the result
with a domain-specific TTL and falls back to cached PostGIS rows when the
provider is unavailable.
"""

from sqlmodel import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.map.models import FuelStation, TruckRestriction
from app.map.repository import (
    FuelStationRepository,
    TrafficSnapshotRepository,
    TruckRestrictionRepository,
)
from app.providers.base import (
    FuelStationProvider,
    TrafficProvider,
    TruckRestrictionProvider,
)
from app.providers.exceptions import ProviderError
from app.providers.geo import GeoJSONPoint, point_to_wkt
from app.providers.schemas import (
    FuelStationData,
    LayerQuery,
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
            "truck_accessible": station.truck_accessible,
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
