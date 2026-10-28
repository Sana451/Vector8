"""
HERE Routing adapter.

Implements RoutingProvider using HERE Routing API v8.
"""

from __future__ import annotations

from typing import Any, ClassVar

import httpx
from flexpolyline import decode  # type: ignore[import-untyped]
from pydantic import ValidationError

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.exceptions import ProviderError, ProviderTimeoutError
from app.providers.geo import GeoJSONLineString
from app.providers.here.constants import (
    MAX_VIA_POINTS_PER_REQUEST,
    PROVIDER_NAME,
    ROUTES_PATH,
)
from app.providers.http import ProviderHTTPClient
from app.routing.exceptions import (
    RoutingAuthenticationError,
    RoutingBadRequestError,
    RoutingProviderError,
    RoutingRateLimitError,
    RoutingTimeoutError,
    RoutingUnavailableError,
)
from app.routing.schemas import (
    CalculateRouteRequest,
    CalculateRouteResponse,
    Leg,
    Route,
    RouteSummary,
    VehicleRoutingProfile,
)

logger = get_logger(__name__)

Coordinate = tuple[float, float]


class HereRoutingProvider:
    """HERE Routing API v8 adapter."""

    provider_name: ClassVar[str] = PROVIDER_NAME

    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client
        self.api_key = settings.HERE_API_KEY
        self.base_url = settings.HERE_ROUTING_BASE_URL.rstrip("/")
        self.timeout = settings.HERE_TIMEOUT_SECONDS

    def _http(self):
        return ProviderHTTPClient(
            provider=PROVIDER_NAME,
            base_url=self.base_url,
            timeout=self.timeout,
            api_key=self.api_key,
            client=self.client,
            error_handler=self._handle_error_response,
        )

    async def calculate_route(
        self,
        request: CalculateRouteRequest,
    ) -> CalculateRouteResponse:
        if not self.api_key:
            raise RoutingAuthenticationError(
                "HERE_API_KEY is not configured",
                provider=PROVIDER_NAME,
            )

        api_key = self.api_key
        segments = self._split_into_segments(request)

        logger.info(
            "Calculating HERE route",
            provider=PROVIDER_NAME,
            segments=len(segments),
        )

        payloads = [
            await self._request_segment(
                request,
                api_key=api_key,
                origin=origin,
                via=via,
                destination=destination,
            )
            for origin, via, destination in segments
        ]

        try:
            return self._transform_response(payloads)
        except (ValidationError, KeyError) as exc:
            raise RoutingProviderError(
                f"Invalid HERE response: {exc}",
                provider=PROVIDER_NAME,
            ) from exc

    async def _request_segment(
        self,
        request: CalculateRouteRequest,
        *,
        api_key: str,
        origin: Coordinate,
        via: list[Coordinate],
        destination: Coordinate,
    ) -> dict[str, Any]:
        params = self._build_params(
            request,
            api_key=api_key,
            origin=origin,
            via=via,
            destination=destination,
        )

        try:
            return await self._http().request_json(
                "GET",
                ROUTES_PATH,
                params=params,
            )
        except ProviderTimeoutError as exc:
            raise RoutingTimeoutError(
                exc.message,
                provider=PROVIDER_NAME,
            ) from exc
        except ProviderError as exc:
            raise RoutingProviderError(
                exc.message,
                provider=PROVIDER_NAME,
            ) from exc

    @staticmethod
    def _waypoints(request: CalculateRouteRequest) -> list[Coordinate]:
        waypoints = request.route_planning_locations.waypoints
        if waypoints is None:
            return []
        return [(float(lon), float(lat)) for lon, lat in waypoints.coordinates]

    @classmethod
    def _split_into_segments(
        cls,
        request: CalculateRouteRequest,
    ) -> list[tuple[Coordinate, list[Coordinate], Coordinate]]:
        """Split a request into chunks that each fit into a single HERE call.

        HERE Routing v8 is queried over GET, so the number of ``via`` points is
        bounded by the maximum URL length. Longer itineraries are cut at a
        waypoint, which then terminates one segment and starts the next one, so
        that every waypoint is still visited exactly once.
        """
        locations = request.route_planning_locations
        origin = locations.origin.coordinates
        destination = locations.destination.coordinates
        via = cls._waypoints(request)

        if len(via) <= MAX_VIA_POINTS_PER_REQUEST:
            return [(origin, via, destination)]

        segments: list[tuple[Coordinate, list[Coordinate], Coordinate]] = []
        start = origin
        index = 0

        while index < len(via):
            chunk = via[index : index + MAX_VIA_POINTS_PER_REQUEST]
            index += MAX_VIA_POINTS_PER_REQUEST

            if index < len(via):
                # The next waypoint closes this segment and opens the next one.
                end = via[index]
                index += 1
            else:
                end = destination

            segments.append((start, chunk, end))
            start = end

        return segments

    def _build_params(
        self,
        request: CalculateRouteRequest,
        *,
        api_key: str,
        origin: Coordinate | None = None,
        via: list[Coordinate] | None = None,
        destination: Coordinate | None = None,
    ) -> dict[str, Any]:
        """Build query parameters for a single HERE call.

        ``origin``, ``via`` and ``destination`` describe one segment of a split
        itinerary. When omitted, they are taken from the request as a whole.
        """
        locations = request.route_planning_locations

        if origin is None:
            origin = locations.origin.coordinates
        if destination is None:
            destination = locations.destination.coordinates
        if via is None:
            via = self._waypoints(request)

        params: dict[str, Any] = {
            "apikey": api_key,
            "origin": f"{origin[1]},{origin[0]}",
            "destination": f"{destination[1]},{destination[0]}",
            "transportMode": "truck",
            "routingMode": self._routing_mode(request),
            "return": "polyline,summary",
        }

        if via:
            # HERE expects ``via`` to be repeated once per waypoint; httpx
            # expands a list into repeated query parameters.
            stop_duration = locations.waypoint_stop_duration_seconds
            suffix = (
                f"!stopDuration={stop_duration}" if stop_duration is not None else ""
            )
            params["via"] = [f"{lat},{lon}{suffix}" for lon, lat in via]

        if request.vehicle is not None:
            params.update(self.vehicle_params(request.vehicle))

        return params

    @staticmethod
    def vehicle_params(vehicle: VehicleRoutingProfile) -> dict[str, str]:
        """Map a metric vehicle profile onto HERE ``vehicle[...]`` parameters."""
        values: dict[str, Any] = {
            "type": vehicle.vehicle_type,
            "height": vehicle.height_cm,
            "width": vehicle.width_cm,
            "length": vehicle.length_cm,
            "grossWeight": vehicle.gross_weight_kg,
            "weightPerAxle": vehicle.weight_per_axle_kg,
            "axleCount": vehicle.axle_count,
            "tiresCount": vehicle.tires_count,
            "trailerCount": vehicle.trailer_count or None,
            "trailerLength": vehicle.trailer_length_cm,
            "kpraLength": vehicle.kpra_length_cm,
            "payloadCapacity": vehicle.payload_capacity_kg,
            "speedCap": vehicle.speed_cap_mps,
        }
        return {
            f"vehicle[{name}]": str(value)
            for name, value in values.items()
            if value is not None
        }

    @staticmethod
    def _routing_mode(request: CalculateRouteRequest) -> str:
        if request.route_type is None:
            return "fast"

        mapping = {
            "fast": "fast",
            "short": "short",
            "efficient": "balanced",
        }

        return mapping.get(request.route_type.value, "fast")

    def _transform_response(
        self,
        payloads: list[dict[str, Any]],
    ) -> CalculateRouteResponse:
        """Merge one payload per segment into a single canonical route."""
        legs: list[Leg] = []
        total_length = 0
        total_duration = 0

        for payload in payloads:
            routes = payload["routes"]
            if not routes:
                raise RoutingProviderError(
                    "HERE returned no route",
                    provider=PROVIDER_NAME,
                )

            # Segments are consecutive parts of one itinerary, so only the
            # primary route of each payload can be stitched together.
            for section in routes[0]["sections"]:
                summary = section["summary"]

                total_length += summary["length"]
                total_duration += summary["duration"]

                polyline = decode(section["polyline"])
                coordinates = [(float(lon), float(lat)) for lat, lon in polyline]

                legs.append(
                    Leg(
                        summary=self._summary(
                            length=summary["length"],
                            duration=summary["duration"],
                        ),
                        path=GeoJSONLineString(coordinates=coordinates),
                    )
                )

        return CalculateRouteResponse(
            routes=[
                Route(
                    summary=self._summary(
                        length=total_length,
                        duration=total_duration,
                    ),
                    legs=legs,
                    sections=[],
                )
            ],
            formatVersion="here-v8",
        )

    @staticmethod
    def _summary(*, length: int, duration: int) -> RouteSummary:
        return RouteSummary(
            lengthInMeters=length,
            travelDurationInSeconds=duration,
            trafficDelayDurationInSeconds=None,
            trafficLengthInMeters=None,
            departureDateTime=None,
            arrivalDateTime=None,
            deviationDistanceInMeters=None,
            deviationDurationInSeconds=None,
            deviationPoint=None,
            progressPoints=None,
        )

    def _handle_error_response(
        self,
        response: httpx.Response,
    ):
        code = response.status_code

        if code == 400:
            raise RoutingBadRequestError(
                "Invalid HERE request",
                provider=PROVIDER_NAME,
            )

        if code == 401:
            raise RoutingAuthenticationError(
                "Invalid HERE API key",
                provider=PROVIDER_NAME,
            )

        if code == 403:
            raise RoutingAuthenticationError(
                "HERE authentication failed",
                provider=PROVIDER_NAME,
            )

        if code == 429:
            raise RoutingRateLimitError(
                "HERE rate limit exceeded",
                provider=PROVIDER_NAME,
            )

        if code in (500, 502, 503, 504):
            raise RoutingUnavailableError(
                f"HERE unavailable ({code})",
                provider=PROVIDER_NAME,
            )

        raise RoutingProviderError(
            f"HERE error ({code})",
            provider=PROVIDER_NAME,
        )
