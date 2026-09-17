"""
TomTom routing provider implementation.

Handles integration with TomTom Orbis Maps Routing API v3.
"""

from typing import Any, cast

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.core.logging import get_logger
from app.routing.constants import (
    HEADER_TOMTOM_API_KEY,
    HEADER_TOMTOM_API_VERSION,
    HEADER_TRACKING_ID,
    TOMTOM_CALCULATE_ROUTE_PATH,
)
from app.routing.exceptions import (
    PROVIDER_ERROR_MAPPING,
    RoutingAuthenticationError,
    RoutingBadRequestError,
    RoutingProviderError,
    RoutingRateLimitError,
    RoutingTimeoutError,
    RoutingUnavailableError,
)
from app.routing.providers.base import RoutingProvider
from app.routing.schemas import (
    CalculateRouteRequest,
    CalculateRouteResponse,
)
from app.routing.utils import (
    build_attributes_header,
    generate_tracking_id,
    mask_api_key,
)

logger = get_logger(__name__)


class TomTomProvider(RoutingProvider):
    """TomTom routing provider.

    Implements routing via TomTom Orbis Maps Routing API v3.

    Handles:
    - URL construction
    - Authentication
    - Request transformation
    - Response parsing
    - Error mapping
    - Timeout management
    """

    def __init__(self, client: httpx.AsyncClient | None = None):
        """Initialize TomTom provider.

        Args:
            client: Optional httpx AsyncClient for HTTP requests.
                   If not provided, one will be created per request.
        """
        self.client = client
        self.api_key = settings.TOMTOM_API_KEY
        self.base_url = settings.TOMTOM_BASE_URL
        self.api_version = settings.TOMTOM_API_VERSION
        self.timeout = settings.TOMTOM_TIMEOUT_SECONDS

    async def calculate_route(
        self,
        request: CalculateRouteRequest,
    ) -> CalculateRouteResponse:
        """Calculate route using TomTom API.

        Args:
            request: Route calculation request

        Returns:
            Calculated route response

        Raises:
            RoutingError: Various routing errors depending on API response
        """
        # Generate or use provided tracking ID
        tracking_id = request.tracking_id or generate_tracking_id()

        logger.info(
            "Calculating route",
            tracking_id=tracking_id,
            provider="tomtom",
            api_version=self.api_version,
        )

        # Transform request to TomTom format
        tomtom_request = self._transform_request(request)

        # Prepare headers
        headers = self._prepare_headers(request, tracking_id)

        # Make HTTP request
        url = f"{self.base_url}{TOMTOM_CALCULATE_ROUTE_PATH}"

        try:
            response: httpx.Response | None = None
            if self.client:
                response = await self.client.post(
                    url,
                    json=tomtom_request,
                    headers=headers,
                    timeout=self.timeout,
                )
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        url,
                        json=tomtom_request,
                        headers=headers,
                    )

            logger.info(
                "TomTom API response",
                tracking_id=tracking_id,
                status_code=response.status_code,
                provider="tomtom",
            )

            # Handle HTTP errors
            if response.status_code != 200:
                await self._handle_error_response(
                    response,
                    tracking_id,
                )

            # Parse and validate response
            response_data = response.json()

            try:
                calculated_response = CalculateRouteResponse.model_validate(
                    response_data
                )
            except ValidationError as e:
                logger.error(
                    "Failed to parse TomTom response",
                    tracking_id=tracking_id,
                    error=str(e),
                    provider="tomtom",
                )
                raise RoutingProviderError(
                    f"Invalid response format: {str(e)}",
                    provider="tomtom",
                    status_code=response.status_code,
                )

            return calculated_response

        except httpx.TimeoutException:
            logger.error(
                "TomTom request timeout",
                tracking_id=tracking_id,
                timeout_seconds=self.timeout,
                provider="tomtom",
            )
            raise RoutingTimeoutError(
                f"Request timeout after {self.timeout} seconds",
                provider="tomtom",
            )
        except httpx.HTTPError as e:
            logger.error(
                "TomTom HTTP error",
                tracking_id=tracking_id,
                error=str(e),
                provider="tomtom",
            )
            raise RoutingProviderError(
                str(e),
                provider="tomtom",
            )

    def _transform_request(self, request: CalculateRouteRequest) -> dict[str, Any]:
        """Transform application request to TomTom API format.

        Args:
            request: Application request

        Returns:
            TomTom API request body
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

        # Add waypoints if provided
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

        # Add path if provided
        if request.path:
            tomtom_request["path"] = {
                "type": request.path.type,
                "coordinates": [list(coord) for coord in request.path.coordinates],
            }

        # Add legs if provided
        if request.legs:
            tomtom_request["legs"] = [self._transform_leg(leg) for leg in request.legs]

        # Add avoids
        if request.avoids:
            tomtom_request["avoids"] = [avoid.value for avoid in request.avoids]

        # Add avoid areas
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

        # Add route options
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

        # Add vehicle parameters
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

        # Add timing
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
            leg: Leg configuration

        Returns:
            TomTom leg configuration
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
            request: Route calculation request
            tracking_id: Tracking ID for correlation

        Returns:
            HTTP headers dictionary
        """
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            HEADER_TOMTOM_API_KEY: self.api_key or "",
            HEADER_TOMTOM_API_VERSION: self.api_version,
            HEADER_TRACKING_ID: tracking_id,
        }

        # Add optional headers
        if request.accept_language:
            headers["Accept-Language"] = request.accept_language

        # Add attributes headers
        # If no attributes specified, default to "routes" (required by TomTom)
        attributes = request.attributes or "routes"
        attributes_headers = build_attributes_header(
            attributes=attributes,
            attributes_exclude=request.attributes_exclude,
        )
        headers.update(attributes_headers)

        return headers

    async def _handle_error_response(
        self,
        response: httpx.Response,
        tracking_id: str,
    ) -> None:
        """Handle error response from TomTom API.

        Args:
            response: HTTP response
            tracking_id: Tracking ID for correlation

        Raises:
            RoutingError: Appropriate routing error
        """
        status_code = response.status_code

        # Handle by status code
        if status_code == 400:
            error_data = response.json()
            provider_code = error_data.get("detailedError", {}).get("code")
            message = error_data.get("detailedError", {}).get("message", "Bad request")

            logger.warning(
                "TomTom bad request",
                tracking_id=tracking_id,
                provider_code=provider_code,
                provider="tomtom",
            )

            # Check for specific error codes
            if provider_code in PROVIDER_ERROR_MAPPING:
                error_class = PROVIDER_ERROR_MAPPING[provider_code]
                raise error_class(
                    message,
                    provider="tomtom",
                    provider_code=provider_code,
                    status_code=status_code,
                )

            raise RoutingBadRequestError(
                message,
                provider="tomtom",
                provider_code=provider_code,
                status_code=status_code,
            )

        elif status_code == 403:
            logger.error(
                "TomTom authentication error",
                tracking_id=tracking_id,
                provider="tomtom",
                api_key=mask_api_key(self.api_key or ""),
            )
            raise RoutingAuthenticationError(
                "Authentication failed - check API key",
                provider="tomtom",
                status_code=status_code,
            )

        elif status_code == 429:
            logger.warning(
                "TomTom rate limit exceeded",
                tracking_id=tracking_id,
                provider="tomtom",
            )
            raise RoutingRateLimitError(
                "Rate limit exceeded",
                provider="tomtom",
                status_code=status_code,
            )

        elif status_code == 408:
            raise RoutingTimeoutError(
                "Request timeout from TomTom",
                provider="tomtom",
                status_code=status_code,
            )

        elif status_code in (502, 503, 504):
            logger.error(
                "TomTom provider error",
                tracking_id=tracking_id,
                status_code=status_code,
                provider="tomtom",
            )
            raise RoutingUnavailableError(
                f"TomTom temporarily unavailable (HTTP {status_code})",
                provider="tomtom",
                status_code=status_code,
            )

        else:
            error_data = response.json()
            message = error_data.get("detailedError", {}).get(
                "message", "Unknown error"
            )

            logger.error(
                "TomTom error",
                tracking_id=tracking_id,
                status_code=status_code,
                error_message=message,
                provider="tomtom",
            )

            raise RoutingProviderError(
                message,
                provider="tomtom",
                status_code=status_code,
            )
