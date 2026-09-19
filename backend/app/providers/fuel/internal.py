"""
Internal fuel station adapter.

Fetches fuel stations from the internal Vector8 fleet API. The adapter is a
regular HTTP provider: when ``FUEL_API_BASE_URL`` is not configured it raises
``ProviderUnavailableError`` so the service layer can fall back to cached
PostGIS rows.
"""

from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.exceptions import ProviderUnavailableError
from app.providers.geo import GeoJSONPoint
from app.providers.http import ProviderHTTPClient
from app.providers.schemas import FuelStationData, LayerQuery

logger = get_logger(__name__)

PROVIDER_NAME = "internal"

FUEL_STATIONS_PATH = "/fuel-stations/search"


class InternalFuelStationProvider:
    """Internal fuel station provider."""

    def __init__(self, client: httpx.AsyncClient | None = None):
        """Initialize the internal fuel station provider.

        Args:
            client: Optional httpx AsyncClient. When omitted, a client is
                created per request.
        """
        self.client = client
        self.api_key = settings.FUEL_API_KEY
        self.base_url = settings.FUEL_API_BASE_URL
        self.timeout = settings.FUEL_API_TIMEOUT_SECONDS

    async def find_stations(self, query: LayerQuery) -> list[FuelStationData]:
        """Find fuel stations along the route corridor.

        Args:
            query: Corridor query with route geometry and radius.

        Returns:
            List of normalized fuel stations.

        Raises:
            ProviderUnavailableError: If the provider is not configured.
            ProviderError: If the provider call fails.
        """
        if not self.base_url:
            raise ProviderUnavailableError(
                "FUEL_API_BASE_URL is not configured",
                provider=PROVIDER_NAME,
            )

        logger.info(
            "Fetching fuel stations",
            provider=PROVIDER_NAME,
            radius_meters=query.radius_meters,
            points=len(query.coordinates),
        )

        http = ProviderHTTPClient(
            provider=PROVIDER_NAME,
            base_url=self.base_url,
            timeout=self.timeout,
            api_key=self.api_key,
            client=self.client,
            default_headers=self._auth_headers(),
        )

        payload = await http.request_json(
            "POST",
            FUEL_STATIONS_PATH,
            json={
                "path": query.path.model_dump(mode="json"),
                "radius_meters": query.radius_meters,
                "limit": query.limit,
            },
        )

        return self._parse(payload)

    def _auth_headers(self) -> dict[str, str]:
        """Build authentication headers when an API key is configured."""
        if not self.api_key:
            return {}
        return {"Authorization": f"Bearer {self.api_key}"}

    def _parse(self, payload: Any) -> list[FuelStationData]:
        """Normalize the provider payload into ``FuelStationData``."""
        items = payload.get("stations") if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            return []

        stations: list[FuelStationData] = []
        for raw in items:
            station = self._parse_station(raw)
            if station is not None:
                stations.append(station)
        return stations

    @staticmethod
    def _parse_station(raw: Any) -> FuelStationData | None:
        """Normalize a single station entry."""
        if not isinstance(raw, dict):
            return None

        external_id = raw.get("id") or raw.get("external_id")
        name = raw.get("name")
        if external_id is None or not name:
            return None

        location = raw.get("location")
        coordinates: Any = None
        if isinstance(location, dict):
            coordinates = location.get("coordinates")
        elif raw.get("longitude") is not None and raw.get("latitude") is not None:
            coordinates = [raw["longitude"], raw["latitude"]]

        if not isinstance(coordinates, list | tuple) or len(coordinates) < 2:
            return None

        try:
            point = GeoJSONPoint(
                coordinates=(float(coordinates[0]), float(coordinates[1]))
            )
        except TypeError, ValueError:
            return None

        diesel_price = raw.get("diesel_price")
        try:
            diesel_price = None if diesel_price is None else float(diesel_price)
        except TypeError, ValueError:
            diesel_price = None

        return FuelStationData(
            external_id=str(external_id),
            name=str(name),
            brand=raw.get("brand"),
            address=raw.get("address"),
            location=point,
            diesel_price=diesel_price,
            truck_accessible=bool(raw.get("truck_accessible", True)),
            raw=raw,
        )
