"""Internal fuel station adapter backed by the local PostGIS catalog."""

from typing import Any

from app.core.logging import get_logger
from app.map.models import FuelStation
from app.map.repository import FuelStationRepository
from app.providers.exceptions import ProviderUnavailableError
from app.providers.schemas import FuelStationData, LayerQuery

logger = get_logger(__name__)

PROVIDER_NAME = "internal"


class InternalFuelStationProvider:
    """Internal fuel station provider."""

    def __init__(
        self,
        client: object | None = None,
        repository: FuelStationRepository | None = None,
    ):
        """Initialize the provider.

        ``client`` is kept only for backward-compatible construction sites; the
        internal provider no longer performs HTTP requests.
        """
        self.client = client
        self.repository = repository

    async def find_stations(self, query: LayerQuery) -> list[FuelStationData]:
        """Find fuel stations along the route corridor."""
        if self.repository is None:
            raise ProviderUnavailableError(
                "Internal fuel provider repository is not configured",
                provider=PROVIDER_NAME,
            )

        logger.info(
            "Reading internal fuel stations from PostGIS",
            provider=PROVIDER_NAME,
            radius_meters=query.radius_meters,
            points=len(query.coordinates),
            limit=query.limit,
        )

        rows = self.repository.find_along_route(
            coordinates=query.coordinates,
            radius_meters=query.radius_meters,
            limit=query.limit,
            provider=PROVIDER_NAME,
        )
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: FuelStation) -> FuelStationData:
        """Rebuild a DTO from a persisted station row."""
        payload: Any = row.payload or {}
        station = FuelStationData.model_validate(payload)
        distance = getattr(row, "distance_to_route_meters", None)
        if not isinstance(distance, int | float):
            return station
        return station.model_copy(update={"distance_meters": float(distance)})
