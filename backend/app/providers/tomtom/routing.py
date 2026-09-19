"""
TomTom routing adapter.

Implements the ``RoutingProvider`` protocol via TomTom Orbis Maps Routing API v3.

Handles URL construction, authentication, request/response transformation,
error mapping and timeout management.
"""

from typing import Any, cast

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.exceptions import ProviderError, ProviderTimeoutError
from app.providers.http import ProviderHTTPClient, mask_api_key
from app.providers.tomtom.constants import (
    HEADER_TOMTOM_API_KEY,
    HEADER_TOMTOM_API_VERSION,
    HEADER_TRACKING_ID,
    TOMTOM_CALCULATE_ROUTE_PATH,
)
from app.routing.exceptions import (
    PROVIDER_ERROR_MAPPING,
    RoutingAuthenticationError,
    RoutingBadRequestError,
    RoutingError,
    RoutingProviderError,
    RoutingRateLimitError,
    RoutingTimeoutError,
    RoutingUnavailableError,
)
from app.routing.schemas import CalculateRouteRequest, CalculateRouteResponse
from app.routing.utils import build_attributes_header, generate_tracking_id

logger = get_logger(__name__)

PROVIDER_NAME = "tomtom"


class TomTomRoutingProvider:
    """TomTom routing provider.

    Implements routing via TomTom Orbis Maps Routing API v3.
    """

    def __init__(self, client: httpx.AsyncClient | None = None):
        """Initialize TomTom routing provider.

        Args:
            client: Optional httpx AsyncClient. When omitted, a client is
                created per request.
        """
        self.client = client
        self.api_key = settings.TOMTOM_API_KEY
        self.base_url = settings.TOMTOM_BASE_URL
        self.api_version = settings.TOMTOM_API_VERSION
        self.timeout = settings.TOMTOM_TIMEOUT_SECONDS

    def _http(self, tracking_id: str) -> ProviderHTTPClient:
        """Build a transport client bound to this provider."""
        return ProviderHTTPClient(
            provider=PROVIDER_NAME,
            base_url=self.base_url,
            timeout=self.timeout,
            api_key=self.api_key,
            client=self.client,
            error_handler=lambda response: self._handle_error_response(
                response, tracking_id
            ),
        )

    async def calculate_route(
        self,
        request: CalculateRouteRequest,
    ) -> CalculateRouteResponse:
        """Calculate route using TomTom API.

        Args:
            request: Route calculation request.

        Returns:
            Calculated route response.

        Raises:
            RoutingError: Various routing errors depending on API response.
        """
        tracking_id = request.tracking_id or generate_tracking_id()

        logger.info(
            "Calculating route",
            tracking_id=tracking_id,
            provider=PROVIDER_NAME,
            api_version=self.api_version,
        )

        tomtom_request = self._transform_request(request)
        headers = self._prepare_headers(request, tracking_id)

        try:
            response_data = await self._http(tracking_id).request_json(
                "POST",
                TOMTOM_CALCULATE_ROUTE_PATH,
                json=tomtom_request,
                headers=headers,
                tracking_id=tracking_id,
            )
        except RoutingError:
            # Already mapped by _handle_error_response.
            raise
        except ProviderTimeoutError as exc:
            raise RoutingTimeoutError(
                exc.message, provider=PROVIDER_NAME, status_code=exc.status_code
            ) from exc
        except ProviderError as exc:
            raise RoutingProviderError(
                exc.message,
                provider=exc.provider or PROVIDER_NAME,
                provider_code=exc.provider_code,
                status_code=exc.status_code,
            ) from exc

        try:
            return CalculateRouteResponse.model_validate(response_data)
        except ValidationError as exc:
            logger.error(
                "Failed to parse TomTom response",
                tracking_id=tracking_id,
                error=str(exc),
                provider=PROVIDER_NAME,
            )
            raise RoutingProviderError(
                f"Invalid response format: {str(exc)}",
                provider=PROVIDER_NAME,
            ) from exc

    def _transform_request(self, request: CalculateRouteRequest) -> dict[str, Any]:
        """Transform application request to TomTom API format.

        Args:
            request: Application request.

        Returns:
            TomTom API request body.
        """
        tomtom_request: dict[str, Any] = {
            "routePlanningLocations": {
                "origin": {
                    "type": request.route_planning_locations.origin.type,
                    "coordinates": list(
                        request.route_planning_locations.origin.coordinates
                    ),
                },
                "destination": {
                    "type": request.route_planning_locations.destination.type,
                    "coordinates": list(
                        request.route_planning_locations.destination.coordinates
                    ),
                },
            },
        }

        if (
            request.route_planning_locations.waypoints
            and request.route_planning_locations.waypoints.coordinates
        ):
            cast(Any, tomtom_request["routePlanningLocations"])["waypoints"] = {
                "type": request.route_planning_locations.waypoints.type,
                "coordinates": [
                    list(coord)
                    for coord in request.route_planning_locations.waypoints.coordinates
                ],
            }

        if request.path:
            tomtom_request["path"] = {
                "type": request.path.type,
                "coordinates": [list(coord) for coord in request.path.coordinates],
            }

        if request.legs:
            tomtom_request["legs"] = [self._transform_leg(leg) for leg in request.legs]

        if request.avoids:
            tomtom_request["avoids"] = [avoid.value for avoid in request.avoids]

        if request.avoid_areas and request.avoid_areas.rectangles:
            tomtom_request["avoidAreas"] = {
                "rectangles": [
                    {
                        "type": rect.type,
                        "geometry": rect.geometry,
                        "bbox": list(rect.bbox),
                    }
                    for rect in request.avoid_areas.rectangles
                ],
            }

        if request.route_type:
            tomtom_request["routeType"] = request.route_type.value
        if request.traffic:
            tomtom_request["traffic"] = request.traffic.value
        if request.max_path_alternative_routes is not None:
            tomtom_request["maxPathAlternativeRoutes"] = (
                request.max_path_alternative_routes
            )
        if request.travel_mode:
            tomtom_request["travelMode"] = request.travel_mode.value
        if request.arrival_side_preference:
            tomtom_request["arrivalSidePreference"] = (
                request.arrival_side_preference.value
            )

        if request.vehicle_heading_in_degrees is not None:
            tomtom_request["vehicleHeadingInDegrees"] = (
                request.vehicle_heading_in_degrees
            )
        if request.vehicle_max_speed_in_kilometers_per_hour is not None:
            tomtom_request["vehicleMaxSpeedInKilometersPerHour"] = (
                request.vehicle_max_speed_in_kilometers_per_hour
            )
        if request.vehicle_weight_in_kilograms is not None:
            tomtom_request["vehicleWeightInKilograms"] = (
                request.vehicle_weight_in_kilograms
            )
        if request.vehicle_engine_type:
            tomtom_request["vehicleEngineType"] = request.vehicle_engine_type.value
        if request.vehicle_has_electronic_toll_collection_transponder:
            tomtom_request["vehicleHasElectronicTollCollectionTransponder"] = (
                request.vehicle_has_electronic_toll_collection_transponder.value
            )

        if request.departure_date_time:
            tomtom_request["departureDateTime"] = (
                request.departure_date_time.isoformat()
            )
        if request.arrival_date_time:
            tomtom_request["arrivalDateTime"] = request.arrival_date_time.isoformat()

        return tomtom_request

    def _transform_leg(self, leg: Any) -> dict[str, Any]:
        """Transform leg configuration to TomTom format.

        Args:
            leg: Leg configuration.

        Returns:
            TomTom leg configuration.
        """
        tomtom_leg: dict[str, Any] = {}

        if leg.route_type:
            tomtom_leg["routeType"] = leg.route_type.value

        if leg.route_stop:
            tomtom_leg["routeStop"] = {}
            if leg.route_stop.pause_duration_in_seconds is not None:
                tomtom_leg["routeStop"]["pauseDurationInSeconds"] = (
                    leg.route_stop.pause_duration_in_seconds
                )
            if leg.route_stop.entry_points:
                tomtom_leg["routeStop"]["entryPoints"] = [
                    {"type": ep.type, "coordinates": list(ep.coordinates)}
                    for ep in leg.route_stop.entry_points
                ]
            if leg.route_stop.preferred_entry_point_index is not None:
                tomtom_leg["routeStop"]["preferredEntryPointIndex"] = (
                    leg.route_stop.preferred_entry_point_index
                )

        if leg.path:
            tomtom_leg["path"] = {
                "type": leg.path.type,
                "coordinates": [list(coord) for coord in leg.path.coordinates],
            }

        if leg.avoids:
            tomtom_leg["avoids"] = [avoid.value for avoid in leg.avoids]

        return tomtom_leg

    def _prepare_headers(
        self,
        request: CalculateRouteRequest,
        tracking_id: str,
    ) -> dict[str, str]:
        """Prepare HTTP headers for TomTom request.

        Args:
            request: Route calculation request.
            tracking_id: Tracking ID for correlation.

        Returns:
            HTTP headers dictionary.
        """
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            HEADER_TOMTOM_API_KEY: self.api_key or "",
            HEADER_TOMTOM_API_VERSION: self.api_version,
            HEADER_TRACKING_ID: tracking_id,
        }

        if request.accept_language:
            headers["Accept-Language"] = request.accept_language

        # If no attributes specified, default to "routes" (required by TomTom)
        attributes = request.attributes or "routes"
        headers.update(
            build_attributes_header(
                attributes=attributes,
                attributes_exclude=request.attributes_exclude,
            )
        )

        return headers

    def _handle_error_response(
        self,
        response: httpx.Response,
        tracking_id: str,
    ) -> None:
        """Handle error response from TomTom API.

        Args:
            response: HTTP response.
            tracking_id: Tracking ID for correlation.

        Raises:
            RoutingError: Appropriate routing error.
        """
        status_code = response.status_code

        if status_code == 400:
            error_data = response.json()
            provider_code = error_data.get("detailedError", {}).get("code")
            message = error_data.get("detailedError", {}).get("message", "Bad request")

            logger.warning(
                "TomTom bad request",
                tracking_id=tracking_id,
                provider_code=provider_code,
                provider=PROVIDER_NAME,
            )

            if provider_code in PROVIDER_ERROR_MAPPING:
                error_class = PROVIDER_ERROR_MAPPING[provider_code]
                raise error_class(
                    message,
                    provider=PROVIDER_NAME,
                    provider_code=provider_code,
                    status_code=status_code,
                )

            raise RoutingBadRequestError(
                message,
                provider=PROVIDER_NAME,
                provider_code=provider_code,
                status_code=status_code,
            )

        if status_code == 403:
            logger.error(
                "TomTom authentication error",
                tracking_id=tracking_id,
                provider=PROVIDER_NAME,
                api_key=mask_api_key(self.api_key or ""),
            )
            raise RoutingAuthenticationError(
                "Authentication failed - check API key",
                provider=PROVIDER_NAME,
                status_code=status_code,
            )

        if status_code == 429:
            logger.warning(
                "TomTom rate limit exceeded",
                tracking_id=tracking_id,
                provider=PROVIDER_NAME,
            )
            raise RoutingRateLimitError(
                "Rate limit exceeded",
                provider=PROVIDER_NAME,
                status_code=status_code,
            )

        if status_code == 408:
            raise RoutingTimeoutError(
                "Request timeout from TomTom",
                provider=PROVIDER_NAME,
                status_code=status_code,
            )

        if status_code in (502, 503, 504):
            logger.error(
                "TomTom provider error",
                tracking_id=tracking_id,
                status_code=status_code,
                provider=PROVIDER_NAME,
            )
            raise RoutingUnavailableError(
                f"TomTom temporarily unavailable (HTTP {status_code})",
                provider=PROVIDER_NAME,
                status_code=status_code,
            )

        error_data = response.json()
        message = error_data.get("detailedError", {}).get("message", "Unknown error")

        logger.error(
            "TomTom error",
            tracking_id=tracking_id,
            status_code=status_code,
            error_message=message,
            provider=PROVIDER_NAME,
        )

        raise RoutingProviderError(
            message,
            provider=PROVIDER_NAME,
            status_code=status_code,
        )
