"""HERE Fuel Prices adapter for truck diesel stations along a route."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.exceptions import ProviderBadRequestError, ProviderUnavailableError
from app.providers.geo import GeoJSONPoint, simplify_route_for_here
from app.providers.http import ProviderHTTPClient
from app.providers.schemas import FuelStationData, LayerQuery

logger = get_logger(__name__)

PROVIDER_NAME = "here"
FUEL_STATIONS_PATH = "/v3/stations"
TRUCK_DIESEL_FUEL_TYPE = 11
ADBLUE_FUEL_TYPE = 72
TRUCK_DIESEL_LABEL = "Truck Diesel"
PRICE_SORT = "price:asc"
HERE_FUEL_ROUTE_TARGET_POINTS = 100
HERE_FUEL_ROUTE_MAX_ENCODED_LENGTH = 800


class HereFuelProvider:
    """Fetch truck diesel stations from HERE Fuel Prices API."""

    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client
        self.api_key = settings.HERE_API_KEY
        self.base_url = settings.HERE_FUEL_BASE_URL.rstrip("/")
        self.timeout = settings.HERE_TIMEOUT_SECONDS
        self.max_width = settings.HERE_FUEL_CORRIDOR_WIDTH
        self.max_limit = settings.HERE_FUEL_LIMIT

    async def find_stations(self, query: LayerQuery) -> list[FuelStationData]:
        """Find truck diesel stations along the route corridor."""
        if not self.api_key:
            raise ProviderUnavailableError(
                "HERE_API_KEY is not configured",
                provider=PROVIDER_NAME,
            )

        width = min(query.radius_meters, self.max_width)
        limit = min(query.limit, self.max_limit)
        corridor = self._build_corridor(query)

        logger.info(
            "Fetching HERE fuel stations",
            provider=PROVIDER_NAME,
            fuel_type=TRUCK_DIESEL_LABEL,
            sort="price",
            width=width,
            points=len(query.coordinates),
            corridor_points=len(corridor),
            limit=limit,
        )

        http = ProviderHTTPClient(
            provider=PROVIDER_NAME,
            base_url=self.base_url,
            timeout=self.timeout,
            api_key=self.api_key,
            client=self.client,
            error_handler=self._handle_error_response,
        )
        payload = await http.request_json(
            "POST",
            FUEL_STATIONS_PATH,
            params={
                "apiKey": self.api_key,
                "fuelTypes": str(TRUCK_DIESEL_FUEL_TYPE),
                "limit": limit,
                "sort": PRICE_SORT,
                "returnAllStations": "true",
            },
            json={
                "corridor": corridor,
                "width": width,
            },
        )

        stations = self._parse(payload)
        logger.info(
            "HERE fuel stations parsed",
            provider=PROVIDER_NAME,
            fuel_type=TRUCK_DIESEL_LABEL,
            sort="price",
            width=width,
            stations_count=len(stations),
        )
        return stations

    def _build_corridor(self, query: LayerQuery) -> list[dict[str, float]]:
        simplified = simplify_route_for_here(
            query.coordinates,
            target_points=HERE_FUEL_ROUTE_TARGET_POINTS,
            max_encoded_length=HERE_FUEL_ROUTE_MAX_ENCODED_LENGTH,
        )
        if len(simplified) < len(query.coordinates):
            logger.info(
                "Simplified HERE fuel corridor",
                provider=PROVIDER_NAME,
                original_points=len(query.coordinates),
                simplified_points=len(simplified),
            )
        return [{"lat": lat, "lng": lon} for lon, lat in simplified]

    @staticmethod
    def _handle_error_response(response: httpx.Response) -> None:
        if response.status_code == 413:
            raise ProviderBadRequestError(
                "HERE fuel corridor request is too large; the route exceeds provider corridor limits",
                provider=PROVIDER_NAME,
                status_code=413,
            )

    def _parse(self, payload: Any) -> list[FuelStationData]:
        items = self._extract_items(payload)
        stations: list[FuelStationData] = []
        for raw in items:
            station = self._parse_station(raw)
            if station is not None:
                stations.append(station)
        return stations

    def _extract_items(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            raise ProviderBadRequestError(
                "Invalid HERE fuel response payload",
                provider=PROVIDER_NAME,
            )

        for key in ("stations", "items", "results"):
            items = payload.get(key)
            if items is None:
                continue
            if not isinstance(items, list):
                raise ProviderBadRequestError(
                    f"HERE fuel response field '{key}' is not an array",
                    provider=PROVIDER_NAME,
                )
            return [item for item in items if isinstance(item, dict)]
        return []

    def _parse_station(self, raw: dict[str, Any]) -> FuelStationData | None:
        external_id = self._as_str(raw.get("id"))
        name = self._as_str(raw.get("name") or raw.get("title"))
        point = self._point_from_here(raw.get("location") or raw.get("position"))
        if external_id is None or name is None or point is None:
            return None

        fuel_info = self._fuel_info(raw.get("fuels"))
        adblue_present = self._has_fuel_type(raw.get("fuels"), ADBLUE_FUEL_TYPE)
        contacts = self._contacts(raw.get("contacts"))
        opening_hours = self._opening_hours(raw.get("openingHours"))

        return FuelStationData(
            external_id=external_id,
            name=name,
            brand=self._brand(raw.get("brand")),
            address=self._address(raw.get("address")),
            location=point,
            diesel_price=self._as_float(fuel_info.get("price")),
            currency=self._as_str(fuel_info.get("currency") or raw.get("currency")),
            fuel_type=TRUCK_DIESEL_LABEL,
            distance_meters=self._as_float(raw.get("distance")),
            is_open=self._is_open(opening_hours),
            opening_hours=opening_hours,
            phone=self._first_contact_value(contacts, "phone"),
            website=self._first_contact_value(contacts, "www"),
            has_adblue=adblue_present,
            truck_accessible=self._truck_accessible(raw),
            raw=raw,
        )

    @staticmethod
    def _point_from_here(raw: Any) -> GeoJSONPoint | None:
        if not isinstance(raw, dict):
            return None
        try:
            lat = float(raw["lat"])
            lon = float(raw["lng"])
        except KeyError, TypeError, ValueError:
            return None
        return GeoJSONPoint(coordinates=(lon, lat))

    @staticmethod
    def _brand(raw: Any) -> str | None:
        if isinstance(raw, dict):
            return HereFuelProvider._as_str(raw.get("name") or raw.get("label"))
        return HereFuelProvider._as_str(raw)

    @staticmethod
    def _address(raw: Any) -> str | None:
        if isinstance(raw, dict):
            return HereFuelProvider._as_str(raw.get("label"))
        return HereFuelProvider._as_str(raw)

    @staticmethod
    def _contacts(raw: Any) -> list[dict[str, Any]]:
        if isinstance(raw, dict):
            return [raw]
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
        return []

    @staticmethod
    def _opening_hours(raw: Any) -> list[dict[str, Any]]:
        if isinstance(raw, dict):
            return [raw]
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
        return []

    @staticmethod
    def _is_open(opening_hours: list[dict[str, Any]]) -> bool | None:
        for entry in opening_hours:
            is_open = entry.get("isOpen")
            if isinstance(is_open, bool):
                return is_open
        return None

    @staticmethod
    def _truck_accessible(raw: dict[str, Any]) -> bool:
        explicit = raw.get("truckAccessible")
        if isinstance(explicit, bool):
            return explicit
        return True

    @staticmethod
    def _fuel_info(raw: Any) -> dict[str, Any]:
        if not isinstance(raw, list):
            return {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            if HereFuelProvider._fuel_type_matches(
                item.get("fuelType"), TRUCK_DIESEL_FUEL_TYPE
            ):
                return item
        return {}

    @staticmethod
    def _has_fuel_type(raw: Any, fuel_type: int) -> bool:
        if not isinstance(raw, list):
            return False
        return any(
            isinstance(item, dict)
            and HereFuelProvider._fuel_type_matches(item.get("fuelType"), fuel_type)
            for item in raw
        )

    @staticmethod
    def _fuel_type_matches(value: Any, expected: int) -> bool:
        if value is None:
            return False
        try:
            return int(value) == expected
        except TypeError, ValueError:
            return str(value).strip() == str(expected)

    @staticmethod
    def _first_contact_value(
        raw_contacts: list[dict[str, Any]], key: str
    ) -> str | None:
        for contact in raw_contacts:
            value = contact.get(key)
            extracted = HereFuelProvider._contact_value(value)
            if extracted is not None:
                return extracted
        return None

    @staticmethod
    def _contact_value(value: Any) -> str | None:
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return HereFuelProvider._as_str(value.get("value") or value.get("href"))
        if isinstance(value, list):
            for item in value:
                extracted = HereFuelProvider._contact_value(item)
                if extracted is not None:
                    return extracted
        return None

    @staticmethod
    def _as_str(value: Any) -> str | None:
        return None if value is None else str(value)

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except TypeError, ValueError:
            return None
