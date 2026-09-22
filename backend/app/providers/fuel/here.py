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
PHONE_CONTACT_KEYS = ("phone", "phones", "tel", "telephone")
WEBSITE_CONTACT_KEYS = ("www", "website", "websites", "url", "urls")
PAGINATION_KEYS = (
    "hasMore",
    "offset",
    "limit",
    "page",
    "pageSize",
    "total",
    "totalCount",
    "count",
    "next",
    "nextPage",
    "nextPageToken",
    "cursor",
)
PAGINATION_CONTAINER_KEYS = ("paging", "pagination", "pageInfo", "metadata")


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

        self._log_response_payload(payload, requested_limit=limit)
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
        _items_key, items = self._extract_items_with_source(payload)
        return items

    def _extract_items_with_source(
        self, payload: Any
    ) -> tuple[str | None, list[dict[str, Any]]]:
        if isinstance(payload, list):
            return None, [item for item in payload if isinstance(item, dict)]
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
            return key, [item for item in items if isinstance(item, dict)]
        return None, []

    def _log_response_payload(self, payload: Any, *, requested_limit: int) -> None:
        items_key, items = self._extract_items_with_source(payload)
        pagination = self._pagination_metadata(payload)
        first_item_keys = sorted(items[0].keys()) if items else []

        logger.info(
            "HERE fuel raw response payload",
            provider=PROVIDER_NAME,
            requested_limit=requested_limit,
            response_type=type(payload).__name__,
            items_key=items_key,
            items_count=len(items),
            top_level_keys=sorted(payload.keys()) if isinstance(payload, dict) else [],
            first_item_keys=first_item_keys,
            pagination=pagination,
            payload=payload,
        )

        if self._looks_paginated(
            items_count=len(items),
            requested_limit=requested_limit,
            pagination=pagination,
        ):
            logger.warning(
                "HERE fuel response may be paginated or truncated",
                provider=PROVIDER_NAME,
                requested_limit=requested_limit,
                items_count=len(items),
                pagination=pagination,
            )

    @staticmethod
    def _pagination_metadata(payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}

        metadata = {
            key: payload[key]
            for key in PAGINATION_KEYS
            if key in payload and payload[key] is not None
        }
        for container_key in PAGINATION_CONTAINER_KEYS:
            container = payload.get(container_key)
            if not isinstance(container, dict):
                continue
            nested = {
                key: container[key]
                for key in PAGINATION_KEYS
                if key in container and container[key] is not None
            }
            if nested:
                metadata[container_key] = nested
        return metadata

    @staticmethod
    def _looks_paginated(
        *,
        items_count: int,
        requested_limit: int,
        pagination: dict[str, Any],
    ) -> bool:
        if not pagination:
            return (
                items_count > 0
                and requested_limit > 0
                and items_count >= requested_limit
            )

        if pagination.get("hasMore") is True:
            return True
        if any(
            key in pagination for key in ("next", "nextPage", "nextPageToken", "cursor")
        ):
            return True
        for container_key in PAGINATION_CONTAINER_KEYS:
            container = pagination.get(container_key)
            if not isinstance(container, dict):
                continue
            if container.get("hasMore") is True:
                return True
            if any(
                key in container
                for key in ("next", "nextPage", "nextPageToken", "cursor")
            ):
                return True

        return (
            items_count > 0 and requested_limit > 0 and items_count >= requested_limit
        )

    def _parse_station(self, raw: dict[str, Any]) -> FuelStationData | None:
        external_id = self._as_str(raw.get("id"))
        name = self._as_str(raw.get("name") or raw.get("title"))
        point = self._point_from_here(
            raw.get("location") or raw.get("position") or raw.get("access")
        )
        if external_id is None or name is None or point is None:
            return None

        station_details = self._station_details(raw)
        fuel_entries = self._fuel_entries(raw)
        fuel_info = self._fuel_info(fuel_entries)
        adblue_present = self._has_fuel_type(fuel_entries, ADBLUE_FUEL_TYPE)
        contacts = self._contacts(raw.get("contacts"))
        opening_hours = self._opening_hours(
            raw.get("openingHours") or station_details.get("openingHours")
        )

        return FuelStationData(
            external_id=external_id,
            name=name,
            brand=self._brand(raw.get("brand")),
            address=self._address(raw.get("address")),
            location=point,
            diesel_price=self._as_float(fuel_info.get("price")),
            currency=self._as_str(fuel_info.get("currency") or raw.get("currency")),
            fuel_type=TRUCK_DIESEL_LABEL,
            distance_meters=self._distance_meters(raw),
            is_open=self._is_open(opening_hours, raw.get("open24x7")),
            opening_hours=opening_hours,
            phone=self._first_contact_value(contacts, *PHONE_CONTACT_KEYS),
            website=self._first_contact_value(contacts, *WEBSITE_CONTACT_KEYS),
            has_adblue=adblue_present,
            medium_truck_accessible=self._medium_truck_accessible(raw),
            large_truck_accessible=self._large_truck_accessible(raw),
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
    def _is_open(
        opening_hours: list[dict[str, Any]], open_24x7: Any = None
    ) -> bool | None:
        for entry in opening_hours:
            is_open = entry.get("isOpen")
            if isinstance(is_open, bool):
                return is_open
        if open_24x7 is True:
            return True
        return None

    @staticmethod
    def _medium_truck_accessible(raw: dict[str, Any]) -> bool:
        """Check if station is accessible for medium trucks."""
        station_details = HereFuelProvider._station_details(raw)
        if station_details.get("restrictedAccess") is True:
            return False
        accessibilities = station_details.get("accessibilities")
        if isinstance(accessibilities, list):
            normalized = {
                str(item).strip().lower()
                for item in accessibilities
                if item is not None
            }
            # Check for medium trucks
            if any("medium" in item for item in normalized):
                return True
            if any("truck" in item for item in normalized):
                return True
            # If accessibilities exist but no truck mention, not accessible
            if normalized:
                return False
        return True

    @staticmethod
    def _large_truck_accessible(raw: dict[str, Any]) -> bool:
        """Check if station is accessible for large trucks."""
        station_details = HereFuelProvider._station_details(raw)
        if station_details.get("restrictedAccess") is True:
            return False
        accessibilities = station_details.get("accessibilities")
        if isinstance(accessibilities, list):
            normalized = {
                str(item).strip().lower()
                for item in accessibilities
                if item is not None
            }
            # Check for large trucks
            if any("large" in item for item in normalized):
                return True
            if any("truck" in item for item in normalized):
                return True
            # If accessibilities exist but no truck mention, not accessible
            if normalized:
                return False
        return True

    @staticmethod
    def _fuel_entries(raw: dict[str, Any]) -> Any:
        fuels = raw.get("fuels")
        if fuels is not None:
            return fuels
        return raw.get("prices")

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
        raw_contacts: list[dict[str, Any]], *keys: str
    ) -> str | None:
        for contact in raw_contacts:
            for key in keys:
                value = contact.get(key)
                extracted = HereFuelProvider._contact_value(value)
                if extracted is not None:
                    return extracted
        return None

    @staticmethod
    def _station_details(raw: dict[str, Any]) -> dict[str, Any]:
        station_details = raw.get("stationDetails")
        if isinstance(station_details, dict):
            return station_details
        return {}

    @staticmethod
    def _distance_meters(raw: dict[str, Any]) -> float | None:
        if "distance" in raw:
            return HereFuelProvider._as_float(raw.get("distance"))
        return HereFuelProvider._as_float(raw.get("distanceMeters"))

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
