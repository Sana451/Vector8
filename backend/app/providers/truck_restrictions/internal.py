"""
Internal truck restriction adapter.

Fetches bridge clearances, weight limits and similar restrictions from the
internal Vector8 compliance API. When ``TRUCK_RESTRICTION_API_BASE_URL`` is not
configured it raises ``ProviderUnavailableError`` so the service layer can fall
back to cached PostGIS rows.
"""

from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.exceptions import ProviderUnavailableError
from app.providers.geo import GeoJSONPoint
from app.providers.http import ProviderHTTPClient
from app.providers.schemas import LayerQuery, RestrictionType, TruckRestrictionData

logger = get_logger(__name__)

PROVIDER_NAME = "internal"

TRUCK_RESTRICTIONS_PATH = "/truck-restrictions/search"


class InternalTruckRestrictionProvider:
    """Internal truck restriction provider."""

    def __init__(self, client: httpx.AsyncClient | None = None):
        """Initialize the internal truck restriction provider.

        Args:
            client: Optional httpx AsyncClient. When omitted, a client is
                created per request.
        """
        self.client = client
        self.api_key = settings.TRUCK_RESTRICTION_API_KEY
        self.base_url = settings.TRUCK_RESTRICTION_API_BASE_URL
        self.timeout = settings.TRUCK_RESTRICTION_API_TIMEOUT_SECONDS

    async def find_restrictions(self, query: LayerQuery) -> list[TruckRestrictionData]:
        """Find truck restrictions along the route corridor.

        Args:
            query: Corridor query with route geometry and radius.

        Returns:
            List of normalized truck restrictions.

        Raises:
            ProviderUnavailableError: If the provider is not configured.
            ProviderError: If the provider call fails.
        """
        if not self.base_url:
            raise ProviderUnavailableError(
                "TRUCK_RESTRICTION_API_BASE_URL is not configured",
                provider=PROVIDER_NAME,
            )

        logger.info(
            "Fetching truck restrictions",
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
            TRUCK_RESTRICTIONS_PATH,
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

    def _parse(self, payload: Any) -> list[TruckRestrictionData]:
        """Normalize the provider payload into ``TruckRestrictionData``."""
        items = payload.get("restrictions") if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            return []

        restrictions: list[TruckRestrictionData] = []
        for raw in items:
            restriction = self._parse_restriction(raw)
            if restriction is not None:
                restrictions.append(restriction)
        return restrictions

    @classmethod
    def _parse_restriction(cls, raw: Any) -> TruckRestrictionData | None:
        """Normalize a single restriction entry."""
        if not isinstance(raw, dict):
            return None

        external_id = raw.get("id") or raw.get("external_id")
        if external_id is None:
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

        return TruckRestrictionData(
            external_id=str(external_id),
            restriction_type=cls._restriction_type(raw.get("restriction_type")),
            description=raw.get("description"),
            location=point,
            max_height_cm=cls._as_int(raw.get("max_height_cm")),
            max_weight_kg=cls._as_int(raw.get("max_weight_kg")),
            max_width_cm=cls._as_int(raw.get("max_width_cm")),
            max_length_cm=cls._as_int(raw.get("max_length_cm")),
            raw=raw,
        )

    @staticmethod
    def _restriction_type(value: Any) -> RestrictionType:
        """Map a provider restriction type onto the normalized enum."""
        if not isinstance(value, str):
            return RestrictionType.OTHER
        try:
            return RestrictionType(value)
        except ValueError:
            return RestrictionType.OTHER

    @staticmethod
    def _as_int(value: Any) -> int | None:
        """Coerce a value to int, returning None on failure."""
        try:
            return int(value)
        except TypeError, ValueError:
            return None
