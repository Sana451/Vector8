"""
HERE Routing adapter.

Implements RoutingProvider using HERE Routing API v8.
"""

from __future__ import annotations

from typing import Any

import httpx
from flexpolyline import decode  # type: ignore[import-untyped]
from pydantic import ValidationError

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.exceptions import ProviderError, ProviderTimeoutError
from app.providers.geo import GeoJSONLineString
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
)

logger = get_logger(__name__)

PROVIDER_NAME = "here"
ROUTES_PATH = "/v8/routes"


class HereRoutingProvider:
    """HERE Routing API v8 adapter."""

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
        params = self._build_params(request, api_key=api_key)

        logger.info(
            "Calculating HERE route",
            provider=PROVIDER_NAME,
        )

        try:
            payload = await self._http().request_json(
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

        try:
            return self._transform_response(payload)
        except ValidationError as exc:
            raise RoutingProviderError(
                f"Invalid HERE response: {exc}",
                provider=PROVIDER_NAME,
            ) from exc

    def _build_params(
        self,
        request: CalculateRouteRequest,
        *,
        api_key: str,
    ) -> dict[str, str]:
        origin = request.route_planning_locations.origin.coordinates
        destination = request.route_planning_locations.destination.coordinates

        params = {
            "apikey": api_key,
            "origin": f"{origin[1]},{origin[0]}",
            "destination": f"{destination[1]},{destination[0]}",
            "transportMode": "truck",
            "routingMode": self._routing_mode(request),
            "return": "polyline,summary",
        }

        if request.route_planning_locations.waypoints:
            params["via"] = "|".join(
                f"{lat},{lon}"
                for lon, lat in request.route_planning_locations.waypoints.coordinates
            )

        return params

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
        payload: dict[str, Any],
    ) -> CalculateRouteResponse:
        routes = []

        for route in payload["routes"]:
            sections = []

            total_length = 0
            total_duration = 0

            for section in route["sections"]:
                summary = section["summary"]

                total_length += summary["length"]
                total_duration += summary["duration"]

                polyline = decode(section["polyline"])

                coordinates = [(float(lon), float(lat)) for lat, lon in polyline]

                sections.append(
                    Leg(
                        summary=RouteSummary(
                            lengthInMeters=summary["length"],
                            travelDurationInSeconds=summary["duration"],
                            trafficDelayDurationInSeconds=None,
                            trafficLengthInMeters=None,
                            departureDateTime=None,
                            arrivalDateTime=None,
                            deviationDistanceInMeters=None,
                            deviationDurationInSeconds=None,
                            deviationPoint=None,
                            progressPoints=None,
                        ),
                        path=GeoJSONLineString(coordinates=coordinates),
                    )
                )

            routes.append(
                Route(
                    summary=RouteSummary(
                        lengthInMeters=total_length,
                        travelDurationInSeconds=total_duration,
                        trafficDelayDurationInSeconds=None,
                        trafficLengthInMeters=None,
                        departureDateTime=None,
                        arrivalDateTime=None,
                        deviationDistanceInMeters=None,
                        deviationDurationInSeconds=None,
                        deviationPoint=None,
                        progressPoints=None,
                    ),
                    legs=sections,
                    sections=[],
                )
            )

        return CalculateRouteResponse(
            routes=routes,
            formatVersion="here-v8",
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
