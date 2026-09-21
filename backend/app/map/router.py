"""
Map API endpoints.

Aggregated map overview combining routing, traffic, fuel stations, truck
restrictions and HERE rest areas into a single response.
"""

from fastapi import APIRouter, HTTPException, Query

from app.map.dependencies import MapLayerServiceDep
from app.map.schemas import MapOverviewRequest, MapOverviewResponse
from app.providers.exceptions import ProviderError

router = APIRouter(
    prefix="/map",
    tags=["map"],
)


@router.post("/route-overview", response_model=MapOverviewResponse)
async def route_overview(
    request: MapOverviewRequest,
    map_service: MapLayerServiceDep,
    force_refresh: bool = Query(
        False, description="Force refresh from providers, skip caches"
    ),
) -> MapOverviewResponse:
    """Build an aggregated map overview for a route.

    Resolves the route first and then fetches every other layer concurrently
    along the resulting corridor.

    Layer behaviour:
    - **route**: mandatory. A routing failure returns 502.
    - **traffic**, **fuel_stations**, **truck_restrictions**, **rest_areas**:
      optional. On failure the layer is empty and the reason is reported in
      `errors`.

    Query parameters:
    - force_refresh: Skip all caches and refresh from providers.

    Args:
        request: Aggregated map request with the route definition.
        map_service: Map layer orchestrator (injected via DI).
        force_refresh: Force refresh from providers.

    Returns:
        Aggregated map overview with per-layer errors.

    Raises:
        HTTPException: 502 when the mandatory route layer fails,
            500 on unexpected errors.
    """
    try:
        return await map_service.get_overview(
            request=request,
            force_refresh=force_refresh,
        )
    except ProviderError as e:
        raise HTTPException(
            status_code=502,
            detail={
                "message": e.message,
                "provider": e.provider,
                "provider_code": e.provider_code,
            },
        ) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error") from e
