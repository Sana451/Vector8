"""Admin fuel endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import SessionDep, get_current_active_superuser
from app.fuel.schemas import PumpPriceImportRequest, PumpPriceImportResponse
from app.fuel.service import PumpPriceImportService
from app.map.repository import FuelStationRepository
from app.providers.exceptions import ProviderAuthenticationError, ProviderError

router = APIRouter(prefix="/fuel", tags=["fuel"])


@router.post(
    "/import/pumpprice",
    response_model=PumpPriceImportResponse,
    dependencies=[Depends(get_current_active_superuser)],
)
async def import_pumpprice_fuel(
    request: PumpPriceImportRequest,
    session: SessionDep,
) -> PumpPriceImportResponse:
    """Synchronously import PumpPrice fuel prices into cached internal stations."""
    service = PumpPriceImportService(FuelStationRepository(session))
    try:
        return await service.import_prices(request)
    except ProviderAuthenticationError as exc:
        raise HTTPException(
            status_code=401,
            detail={
                "message": exc.message,
                "provider": exc.provider,
                "provider_code": exc.provider_code,
            },
        ) from exc
    except ProviderError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": exc.message,
                "provider": exc.provider,
                "provider_code": exc.provider_code,
            },
        ) from exc
