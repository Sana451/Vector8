"""TomTom geocoding provider."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.core.logging import get_logger
from app.geocoding.schemas import GeocodingResult
from app.providers.exceptions import ProviderBadRequestError, ProviderError
from app.providers.geo import GeoJSONPoint
from app.providers.http import ProviderHTTPClient
from app.providers.tomtom.constants import HEADER_TOMTOM_API_KEY

logger = get_logger(__name__)

PROVIDER_NAME = "tomtom"


class TomTomGeocodingProvider:
    """TomTom geocoding adapter."""

    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client
        self.api_key = settings.TOMTOM_API_KEY
        self.base_url = settings.TOMTOM_BASE_URL
        self.timeout = settings.TOMTOM_TIMEOUT_SECONDS

    async def search(self, query: str) -> GeocodingResult:
        logger.info(
            "Geocoding provider request",
            provider=PROVIDER_NAME,
            query_length=len(query),
        )

        http = ProviderHTTPClient(
            provider=PROVIDER_NAME,
            base_url=self.base_url,
            timeout=self.timeout,
            api_key=self.api_key,
            client=self.client,
        )
        path = f"/search/2/geocode/{quote(query, safe='')}.json"
        payload = await http.request_json(
            "GET",
            path,
            params={"key": self.api_key or "", "limit": 1},
            headers={HEADER_TOMTOM_API_KEY: self.api_key or ""},
        )

        result = self._parse_result(payload)
        logger.info(
            "Geocoding provider response",
            provider=PROVIDER_NAME,
            formatted_address=result.formatted_address,
            has_provider_id=result.provider_id is not None,
        )
        return result

    def _parse_result(self, payload: Any) -> GeocodingResult:
        if not isinstance(payload, dict):
            raise ProviderBadRequestError(
                "Invalid geocoding response payload",
                provider=PROVIDER_NAME,
            )

        results = payload.get("results")
        if not isinstance(results, list) or not results:
            raise ProviderBadRequestError(
                "Address could not be geocoded",
                provider=PROVIDER_NAME,
            )

        first = results[0]
        if not isinstance(first, dict):
            raise ProviderBadRequestError(
                "Address could not be geocoded",
                provider=PROVIDER_NAME,
            )

        raw_address = first.get("address")
        address: dict[str, Any] = raw_address if isinstance(raw_address, dict) else {}
        position: dict[str, Any] | None = (
            first.get("position") if isinstance(first.get("position"), dict) else None
        )
        if position is None:
            raise ProviderBadRequestError(
                "Address could not be geocoded",
                provider=PROVIDER_NAME,
            )

        freeform_address = address.get("freeformAddress")
        formatted_address = (
            freeform_address if isinstance(freeform_address, str) else raw_address
        )
        if not isinstance(formatted_address, str) or not formatted_address.strip():
            raise ProviderBadRequestError(
                "Address could not be geocoded",
                provider=PROVIDER_NAME,
            )

        try:
            lon = float(position["lon"])
            lat = float(position["lat"])
            location = GeoJSONPoint(coordinates=(lon, lat))
            return GeocodingResult(
                formatted_address=formatted_address.strip(),
                location=location,
                provider_id=str(first.get("id"))
                if first.get("id") is not None
                else None,
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            logger.error(
                "Failed to parse geocoding response",
                provider=PROVIDER_NAME,
                error=str(exc),
            )
            raise ProviderError(
                f"Invalid geocoding response format: {exc}",
                provider=PROVIDER_NAME,
            ) from exc
