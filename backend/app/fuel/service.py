"""Admin services for importing PumpPrice fuel data into cached fuel stations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.fuel.schemas import (
    PumpPriceImportRequest,
    PumpPriceImportResponse,
)
from app.map.repository import FuelStationRepository
from app.map.services import FuelService
from app.providers.exceptions import (
    ProviderAuthenticationError,
    ProviderError,
)
from app.providers.geo import GeoJSONPoint
from app.providers.http import ProviderHTTPClient
from app.providers.schemas import FuelStationData

logger = get_logger(__name__)

PUMPPRICE_PROVIDER_NAME = "pumpprice"
PERSISTED_PROVIDER_NAME = "internal"
PUMPPRICE_FUEL_PRICES_PATH = "/account/fuel_maps/fuel_prices"
METERS_PER_MILE = 1609.344
NATIONAL_SEARCH_MILES = 2000
NATIONAL_SEARCH_CENTER = (39.8283, -98.5795)

DEFAULT_HEADERS = {
    "accept": "application/json",
    "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "cache-control": "no-cache",
    "content-type": "application/json",
    "priority": "u=1, i",
    "referer": "https://www.pumpprice.co/account/fuel_maps",
    "sec-ch-ua": '"Google Chrome";v="153", "Not_A Brand";v="8", "Chromium";v="153"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
}


class PumpPriceImportService:
    """Synchronously import PumpPrice fuel stations into the local cache table."""

    def __init__(
        self, repository: FuelStationRepository, client: httpx.AsyncClient | None = None
    ):
        self.repository = repository
        self.http = ProviderHTTPClient(
            provider=PUMPPRICE_PROVIDER_NAME,
            base_url=settings.PUMPPRICE_BASE_URL,
            timeout=settings.PUMPPRICE_TIMEOUT_SECONDS,
            client=client,
            default_headers=DEFAULT_HEADERS,
            error_handler=self._log_error_response,
        )

    async def import_prices(
        self,
        request: PumpPriceImportRequest,
    ) -> PumpPriceImportResponse:
        """Run a synchronous nationwide PumpPrice import and persist unique stations."""
        latitude, longitude = NATIONAL_SEARCH_CENTER
        imported_at = datetime.now(UTC)
        unique_stations: dict[str, FuelStationData] = {}
        duplicates_discarded = 0
        stations_received = 0

        logger.info(
            "Fetching PumpPrice fuel prices",
            latitude=latitude,
            longitude=longitude,
            miles=NATIONAL_SEARCH_MILES,
        )
        try:
            payload = await self.http.request_json(
                "GET",
                PUMPPRICE_FUEL_PRICES_PATH,
                params={
                    "miles": NATIONAL_SEARCH_MILES,
                    "lat": latitude,
                    "lng": longitude,
                },
                headers={
                    "Cookie": self._cookie_header(
                        request.fuel_analytics_session,
                    )
                },
                tracking_id="continental_us",
            )
        except ProviderAuthenticationError as exc:
            raise ProviderAuthenticationError(
                "PumpPrice session is invalid or expired; provide a fresh _fuel_analytics_session cookie",
                provider=PUMPPRICE_PROVIDER_NAME,
                status_code=exc.status_code,
            ) from exc
        except ProviderError:
            payload = None

        if payload is not None:
            raw_stations = self._extract_prices(payload)
            stations_received = len(raw_stations)
            for raw in raw_stations:
                station = self._normalize_station(raw)
                if station is None:
                    continue
                dedupe_key = self._dedupe_key(raw, station)
                existing = unique_stations.get(dedupe_key)
                if existing is None:
                    unique_stations[dedupe_key] = station
                    continue
                duplicates_discarded += 1
                unique_stations[dedupe_key] = self._merge_station(existing, station)

        persisted_stations = 0
        if unique_stations:
            persisted_stations = self.repository.upsert_many(
                provider=PERSISTED_PROVIDER_NAME,
                stations=[
                    FuelService._to_row(station, last_imported_at=imported_at)
                    for station in unique_stations.values()
                ],
                ttl_seconds=settings.FUEL_CACHE_TTL_SECONDS,
                persist_internal=True,
            )

        return PumpPriceImportResponse(
            persisted_provider=PERSISTED_PROVIDER_NAME,
            stations_received=stations_received,
            unique_stations=len(unique_stations),
            duplicates_discarded=duplicates_discarded,
            persisted_stations=persisted_stations,
        )

    @staticmethod
    def _cookie_header(session_cookie: str) -> str:
        session_cookie = session_cookie.strip()
        if session_cookie.startswith("_fuel_analytics_session="):
            return session_cookie
        return f"_fuel_analytics_session={session_cookie}"

    def _log_error_response(self, response: httpx.Response) -> None:
        request_headers = self._sanitize_headers(dict(response.request.headers.items()))
        response_headers = self._sanitize_headers(dict(response.headers.items()))

        logger.error(
            "PumpPrice provider returned error response",
            status_code=response.status_code,
            request_url=str(response.request.url),
            request_headers=request_headers,
            response_headers=response_headers,
            response_json=self._response_json_for_logging(response),
            response_text=self._truncate_text(response.text),
        )

    @staticmethod
    def _response_json_for_logging(response: httpx.Response) -> dict[str, Any] | None:
        try:
            parsed = response.json()
        except ValueError:
            return None

        if not isinstance(parsed, dict):
            return None
        return {str(key): value for key, value in parsed.items()}

    @staticmethod
    def _sanitize_headers(headers: Mapping[object, Any]) -> dict[str, str]:
        redacted_names = {"authorization", "cookie", "set-cookie", "x-api-key"}
        sanitized: dict[str, str] = {}
        for key, value in headers.items():
            key_text = str(key)
            if key_text.lower() in redacted_names:
                sanitized[key_text] = "<redacted>"
            else:
                sanitized[key_text] = str(value)
        return sanitized

    @staticmethod
    def _truncate_text(value: str, *, limit: int = 4000) -> str:
        if len(value) <= limit:
            return value
        return f"{value[:limit]}...<truncated {len(value) - limit} chars>"

    @staticmethod
    def _extract_prices(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        result = payload.get("result")
        if not isinstance(result, dict):
            return []
        prices = result.get("fuel_prices")
        if not isinstance(prices, list):
            return []
        return [item for item in prices if isinstance(item, dict)]

    @staticmethod
    def _normalize_station(raw: dict[str, Any]) -> FuelStationData | None:
        external_id = PumpPriceImportService._external_id(raw)
        name = PumpPriceImportService._string(raw.get("store_name"))
        latitude = PumpPriceImportService._float(raw.get("latitude"))
        longitude = PumpPriceImportService._float(raw.get("longitude"))
        if not external_id or not name or latitude is None or longitude is None:
            return None

        price = PumpPriceImportService._float(raw.get("discounted_price"))
        if price is None:
            price = PumpPriceImportService._float(raw.get("retail_price"))

        distance = PumpPriceImportService._float(raw.get("distance"))
        distance_meters = distance * METERS_PER_MILE if distance is not None else None

        address = PumpPriceImportService._address(raw)
        phone = PumpPriceImportService._string(raw.get("phone"))
        website = PumpPriceImportService._string(raw.get("website"))
        brand = PumpPriceImportService._brand(raw, fallback=name)

        return FuelStationData(
            external_id=external_id,
            name=name,
            brand=brand,
            address=address,
            location=GeoJSONPoint(coordinates=(longitude, latitude)),
            diesel_price=price,
            currency="USD",
            fuel_type="Truck Diesel",
            distance_meters=distance_meters,
            phone=phone,
            website=website,
            has_adblue=False,
            medium_truck_accessible=True,
            large_truck_accessible=True,
            raw=raw,
        )

    @staticmethod
    def _external_id(raw: dict[str, Any]) -> str | None:
        for key in ("remote_id", "id"):
            value = raw.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return f"pumpprice:{text}"
        return None

    @staticmethod
    def _address(raw: dict[str, Any]) -> str | None:
        parts = [
            PumpPriceImportService._string(raw.get("street")),
            PumpPriceImportService._string(raw.get("city")),
            PumpPriceImportService._string(raw.get("state")),
            PumpPriceImportService._string(raw.get("country")),
        ]
        values: list[str] = [part for part in parts if part is not None]
        if not values:
            return None
        return ", ".join(values)

    @staticmethod
    def _brand(raw: dict[str, Any], *, fallback: str) -> str:
        store_code = PumpPriceImportService._string(raw.get("store_code"))
        if store_code:
            return store_code
        return fallback

    @staticmethod
    def _dedupe_key(raw: dict[str, Any], station: FuelStationData) -> str:
        remote_id = PumpPriceImportService._string(raw.get("remote_id"))
        if remote_id:
            return f"remote:{remote_id}"
        station_id = PumpPriceImportService._string(raw.get("id"))
        if station_id:
            return f"id:{station_id}"
        lon, lat = station.location.coordinates
        return f"coord:{lat:.5f}:{lon:.5f}:{station.name.strip().lower()}"

    @staticmethod
    def _merge_station(
        existing: FuelStationData,
        candidate: FuelStationData,
    ) -> FuelStationData:
        existing_updated_at = PumpPriceImportService._raw_timestamp(existing.raw)
        candidate_updated_at = PumpPriceImportService._raw_timestamp(candidate.raw)
        if existing.diesel_price is None and candidate.diesel_price is not None:
            return candidate
        if candidate_updated_at and candidate_updated_at > existing_updated_at:
            return candidate
        return existing

    @staticmethod
    def _raw_timestamp(raw: dict[str, Any] | None) -> str:
        if not isinstance(raw, dict):
            return ""
        value = raw.get("updated_at") or raw.get("last_price_change_at")
        return str(value or "")

    @staticmethod
    def _string(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except TypeError, ValueError:
            return None
