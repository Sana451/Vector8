"""
Routing API routes.

HTTP endpoints for routing operations.
"""

from fastapi import APIRouter, HTTPException

from app.routing.dependencies import RoutingServiceDep
from app.routing.exceptions import RoutingError
from app.routing.schemas import CalculateRouteRequest, CalculateRouteResponse

router = APIRouter(
    prefix="/routing",
    tags=["routing"],
)


@router.post("/routes/calculate", response_model=CalculateRouteResponse)
async def calculate_route(
    request: CalculateRouteRequest,
    routing_service: RoutingServiceDep,
) -> CalculateRouteResponse:
    """Calculate route between locations.

    Calculates an optimized route between origin and destination with support for:
    - Multiple waypoints (up to 150)
    - Route alternatives
    - Traffic-aware routing (live or historical)
    - Vehicle-specific parameters (weight, speed, engine type, heading)
    - Avoidances (toll roads, motorways, ferries, unpaved roads, carpool lanes, etc.)
    - Avoid areas (up to 10 rectangular zones)
    - Entry points and route stops
    - Departure/arrival time constraints

    Request schema supports:
    - routePlanningLocations: origin, destination, and optional waypoints
    - routeType: fast, short, efficient, or thrilling
    - traffic: live or historical
    - Vehicle parameters: weight, speed, engine type, heading, toll transponder
    - Various avoidances and constraints

    Returns:
    - One or more calculated routes (based on maxPathAlternativeRoutes)
    - Route summary with distance, duration, and traffic info
    - Detailed legs and sections
    - Progress points for navigation
    - Traffic sections with incident info
    - Country and speed limit sections

    Args:
        request: Route calculation request
        routing_service: Routing service (injected via DI)

    Returns:
        Calculated route response with one or more routes

    Raises:
        HTTPException: Various HTTP errors based on routing provider response
        - 400: Bad request (invalid parameters, no route found)
        - 403: Authentication error (invalid API key)
        - 429: Rate limit exceeded
        - 408: Request timeout
        - 500: Provider error
        - 503: Provider unavailable
    """
    try:
        return await routing_service.calculate_route(request)
    except RoutingError as e:
        # Map routing errors to HTTP exceptions
        # Status code from provider error takes precedence
        status_code = e.status_code or 500
        raise HTTPException(
            status_code=status_code,
            detail={
                "message": e.message,
                "provider": e.provider,
                "provider_code": e.provider_code,
            },
        )
