"""Public geocoding API endpoints."""

from fastapi import APIRouter, HTTPException, Query

from app.geocoding.dependencies import GeocodingServiceDep
from app.geocoding.schemas import GeocodingSearchRequest, GeocodingSearchResponse
from app.providers.exceptions import ProviderError

router = APIRouter(prefix="/geocoding", tags=["geocoding"])


@router.post("/search", response_model=GeocodingSearchResponse)
async def search(
    request: GeocodingSearchRequest,
    geocoding_service: GeocodingServiceDep,
    force_refresh: bool = Query(
        False,
        description="Force refresh from provider, skip geocoding cache",
    ),
) -> GeocodingSearchResponse:
    """Resolve a free-form address query into a single normalized location."""
    try:
        result = await geocoding_service.search(
            request.query,
            force_refresh=force_refresh,
        )
        return GeocodingSearchResponse.from_result(result)
    except ProviderError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": exc.message,
                "provider": exc.provider,
                "provider_code": exc.provider_code,
            },
        ) from exc
