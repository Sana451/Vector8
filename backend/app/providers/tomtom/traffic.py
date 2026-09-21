"""
TomTom traffic adapter.

Implements the ``TrafficProvider`` protocol via the TomTom Traffic Incident
Details API. Incidents are requested for the bounding box of the route
corridor and normalized into provider-agnostic schemas.
"""

import asyncio
import math
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.exceptions import ProviderBadRequestError
from app.providers.geo import GeoJSONPoint
from app.providers.http import ProviderHTTPClient
from app.providers.schemas import (
    LayerQuery,
    TrafficIncident,
    TrafficLayerData,
    TrafficSeverity,
)
from app.providers.tomtom.constants import (
    HEADER_TOMTOM_API_KEY,
    TOMTOM_DELAY_MAGNITUDE_MAP,
    TOMTOM_TRAFFIC_INCIDENTS_PATH,
)

logger = get_logger(__name__)

PROVIDER_NAME = "tomtom"

# Fields requested from the TomTom incident API.
_INCIDENT_FIELDS = (
    "{incidents{type,geometry{type,coordinates},"
    "properties{id,iconCategory,magnitudeOfDelay,events{description,code},"
    "startTime,endTime,delay,length}}}"
)

# Degrees of latitude per meter, used to pad the corridor bounding box.
_METERS_TO_DEGREES = 1 / 111_320
_KILOMETERS_PER_DEGREE = 111.32
_MAX_TOMTOM_BBOX_AREA_SQUARE_KM = 10_000.0
_MAX_BBOX_SPLIT_DEPTH = 12
_BBOX_REQUEST_CONCURRENCY = 8

type BoundingBox = tuple[float, float, float, float]


class TomTomTrafficProvider:
    """TomTom traffic provider."""

    def __init__(self, client: httpx.AsyncClient | None = None):
        """Initialize TomTom traffic provider.

        Args:
            client: Optional httpx AsyncClient. When omitted, a client is
                created per request.
        """
        self.client = client
        self.api_key = settings.TOMTOM_API_KEY
        self.base_url = settings.TOMTOM_BASE_URL
        self.timeout = settings.TOMTOM_TIMEOUT_SECONDS

    async def get_traffic(self, query: LayerQuery) -> TrafficLayerData:
        """Fetch traffic incidents along the route corridor.

        Args:
            query: Corridor query with route geometry and radius.

        Returns:
            Normalized traffic layer payload.

        Raises:
            ProviderError: If the provider call fails.
        """
        bboxes = self._bounding_boxes(query)

        logger.info(
            "Fetching traffic incidents",
            provider=PROVIDER_NAME,
            bbox_count=len(bboxes),
            bbox=bboxes[0] if len(bboxes) == 1 else None,
            radius_meters=query.radius_meters,
        )

        http = ProviderHTTPClient(
            provider=PROVIDER_NAME,
            base_url=self.base_url,
            timeout=self.timeout,
            api_key=self.api_key,
            client=self.client,
        )

        semaphore = asyncio.Semaphore(_BBOX_REQUEST_CONCURRENCY)

        async def fetch_payload(bbox: BoundingBox) -> Any:
            async with semaphore:
                return await http.request_json(
                    "GET",
                    TOMTOM_TRAFFIC_INCIDENTS_PATH,
                    params={
                        "key": self.api_key or "",
                        "bbox": ",".join(str(value) for value in bbox),
                        "fields": _INCIDENT_FIELDS,
                        "language": "en-GB",
                        "timeValidityFilter": "present",
                    },
                    headers={HEADER_TOMTOM_API_KEY: self.api_key or ""},
                )

        payloads = await asyncio.gather(*(fetch_payload(bbox) for bbox in bboxes))
        incidents_by_key: dict[tuple[Any, ...], TrafficIncident] = {}
        for payload in payloads:
            for incident in self._parse_incidents(payload):
                incidents_by_key.setdefault(self._incident_key(incident), incident)

        incidents = list(incidents_by_key.values())

        return TrafficLayerData(
            provider=PROVIDER_NAME,
            incidents=incidents,
            total_delay_seconds=sum(i.delay_seconds or 0 for i in incidents),
            observed_at=datetime.now(UTC),
            raw=self._build_raw_payload(payloads, bboxes),
        )

    @classmethod
    def _bounding_box(cls, query: LayerQuery) -> BoundingBox:
        """Compute a padded bounding box around the route corridor.

        Args:
            query: Corridor query.

        Returns:
            ``(min_lon, min_lat, max_lon, max_lat)``.
        """
        padding = query.radius_meters * _METERS_TO_DEGREES

        return cls._bbox_for_coordinates(query.coordinates, padding)

    @classmethod
    def _bounding_boxes(cls, query: LayerQuery) -> list[BoundingBox]:
        """Split oversized route boxes into TomTom-safe request chunks."""
        padding = query.radius_meters * _METERS_TO_DEGREES
        if any(
            cls._bbox_area_square_km(cls._bbox_for_coordinates([coordinate], padding))
            > _MAX_TOMTOM_BBOX_AREA_SQUARE_KM
            for coordinate in query.coordinates
        ):
            raise ProviderBadRequestError(
                "Traffic search radius is too large for the TomTom incident bbox limit",
                provider=PROVIDER_NAME,
            )

        return cls._split_bounding_boxes(query.coordinates, padding, depth=0)

    @staticmethod
    def _bbox_for_coordinates(
        coordinates: list[tuple[float, float]],
        padding: float,
    ) -> BoundingBox:
        lons = [lon for lon, _ in coordinates]
        lats = [lat for _, lat in coordinates]

        return (
            max(-180.0, min(lons) - padding),
            max(-90.0, min(lats) - padding),
            min(180.0, max(lons) + padding),
            min(90.0, max(lats) + padding),
        )

    @classmethod
    def _split_bounding_boxes(
        cls,
        coordinates: list[tuple[float, float]],
        padding: float,
        *,
        depth: int,
    ) -> list[BoundingBox]:
        bbox = cls._bbox_for_coordinates(coordinates, padding)
        if cls._bbox_area_square_km(bbox) <= _MAX_TOMTOM_BBOX_AREA_SQUARE_KM:
            return [bbox]

        if depth >= _MAX_BBOX_SPLIT_DEPTH:
            raise ProviderBadRequestError(
                "Route corridor exceeds the TomTom incident bbox limit even after splitting",
                provider=PROVIDER_NAME,
            )

        left, right = cls._split_coordinates(coordinates)
        return cls._split_bounding_boxes(
            left, padding, depth=depth + 1
        ) + cls._split_bounding_boxes(
            right,
            padding,
            depth=depth + 1,
        )

    @staticmethod
    def _split_coordinates(
        coordinates: list[tuple[float, float]],
    ) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
        if len(coordinates) > 2:
            midpoint_index = len(coordinates) // 2
            return coordinates[: midpoint_index + 1], coordinates[midpoint_index:]

        start, end = coordinates
        midpoint = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        return [start, midpoint], [midpoint, end]

    @staticmethod
    def _bbox_area_square_km(bbox: BoundingBox) -> float:
        min_lon, min_lat, max_lon, max_lat = bbox
        mean_lat_radians = math.radians((min_lat + max_lat) / 2)
        width_km = (
            (max_lon - min_lon)
            * _KILOMETERS_PER_DEGREE
            * max(
                math.cos(mean_lat_radians),
                1e-6,
            )
        )
        height_km = (max_lat - min_lat) * _KILOMETERS_PER_DEGREE
        return width_km * height_km

    @staticmethod
    def _incident_key(incident: TrafficIncident) -> tuple[Any, ...]:
        if incident.external_id is not None:
            return ("external_id", incident.external_id)
        if incident.location is not None:
            lon, lat = incident.location.coordinates
            return (
                "location",
                round(lon, 6),
                round(lat, 6),
                incident.category,
                incident.description,
                incident.start_time.isoformat() if incident.start_time else None,
            )
        return (
            "fallback",
            incident.category,
            incident.description,
            incident.delay_seconds,
            incident.length_meters,
        )

    @staticmethod
    def _build_raw_payload(
        payloads: list[Any],
        bboxes: list[BoundingBox],
    ) -> dict[str, Any] | None:
        valid_payloads = [payload for payload in payloads if isinstance(payload, dict)]
        if not valid_payloads:
            return None
        if len(valid_payloads) == 1:
            return valid_payloads[0]
        return {
            "responses": valid_payloads,
            "bboxes": [list(bbox) for bbox in bboxes],
        }

    def _parse_incidents(self, payload: Any) -> list[TrafficIncident]:
        """Normalize the TomTom incident payload.

        Args:
            payload: Raw provider response.

        Returns:
            List of normalized incidents.
        """
        if not isinstance(payload, dict):
            return []

        raw_incidents = payload.get("incidents")
        if not isinstance(raw_incidents, list):
            return []

        incidents: list[TrafficIncident] = []
        for raw in raw_incidents:
            if not isinstance(raw, dict):
                continue
            incident = self._parse_incident(raw)
            if incident is not None:
                incidents.append(incident)

        return incidents

    def _parse_incident(self, raw: dict[str, Any]) -> TrafficIncident | None:
        """Normalize a single incident entry."""
        properties = raw.get("properties") or {}
        if not isinstance(properties, dict):
            return None

        events = properties.get("events")
        description = None
        if isinstance(events, list) and events:
            first = events[0]
            if isinstance(first, dict):
                description = first.get("description")

        return TrafficIncident(
            external_id=self._as_str(properties.get("id")),
            severity=self._severity(properties.get("magnitudeOfDelay")),
            category=self._as_str(properties.get("iconCategory")),
            description=description,
            location=self._first_point(raw.get("geometry")),
            delay_seconds=self._as_int(properties.get("delay")),
            length_meters=self._as_int(properties.get("length")),
            start_time=self._as_datetime(properties.get("startTime")),
            end_time=self._as_datetime(properties.get("endTime")),
        )

    @staticmethod
    def _severity(magnitude: Any) -> TrafficSeverity:
        """Map TomTom ``magnitudeOfDelay`` onto normalized severity."""
        try:
            key = int(magnitude)
        except TypeError, ValueError:
            return TrafficSeverity.UNKNOWN
        return TrafficSeverity(TOMTOM_DELAY_MAGNITUDE_MAP.get(key, "unknown"))

    @staticmethod
    def _first_point(geometry: Any) -> GeoJSONPoint | None:
        """Extract a representative point from incident geometry."""
        if not isinstance(geometry, dict):
            return None

        coordinates = geometry.get("coordinates")
        geometry_type = geometry.get("type")

        if geometry_type == "Point" and isinstance(coordinates, list):
            candidate = coordinates
        elif isinstance(coordinates, list) and coordinates:
            candidate = coordinates[0]
        else:
            return None

        if not isinstance(candidate, list) or len(candidate) < 2:
            return None

        try:
            return GeoJSONPoint(coordinates=(float(candidate[0]), float(candidate[1])))
        except TypeError, ValueError:
            return None

    @staticmethod
    def _as_int(value: Any) -> int | None:
        """Coerce a value to int, returning None on failure."""
        try:
            return int(value)
        except TypeError, ValueError:
            return None

    @staticmethod
    def _as_str(value: Any) -> str | None:
        """Coerce a value to str, returning None when absent."""
        return None if value is None else str(value)

    @staticmethod
    def _as_datetime(value: Any) -> datetime | None:
        """Parse an ISO-8601 timestamp, returning None on failure."""
        if not isinstance(value, str) or not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
