"""Admin fuel endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from kombu.exceptions import OperationalError

from app.api.deps import SessionDep, get_current_active_superuser
from app.fuel.schemas import (
    ImportTaskEnqueuedResponse,
    ImportTaskStatusResponse,
    PumpPriceImportMobileResponse,
    PumpPriceImportRequest,
    PumpPriceImportResponse,
)
from app.fuel.service import PumpPriceImportService
from app.fuel.tasks import import_pumpprice_mobile as import_pumpprice_mobile_task
from app.map.repository import FuelStationRepository
from app.providers.exceptions import ProviderAuthenticationError, ProviderError
from app.tasks.celery_app import celery_app
from app.tasks.schedule import PUMPPRICE_MOBILE_IMPORT_TASK

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


@router.post(
    "/import/pumpprice/mobile",
    response_model=PumpPriceImportMobileResponse,
    dependencies=[Depends(get_current_active_superuser)],
)
async def import_pumpprice_mobile(
    session: SessionDep,
) -> PumpPriceImportMobileResponse:
    """Synchronously import PumpPrice mobile fuel prices into cached internal stations."""
    service = PumpPriceImportService(FuelStationRepository(session))
    try:
        return await service.import_prices_mobile()
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


@router.post(
    "/import/pumpprice/mobile/async",
    response_model=ImportTaskEnqueuedResponse,
    status_code=202,
    dependencies=[Depends(get_current_active_superuser)],
)
def enqueue_import_pumpprice_mobile() -> ImportTaskEnqueuedResponse:
    """Enqueue the PumpPrice mobile import as a background Celery task."""
    try:
        result = import_pumpprice_mobile_task.delay()
    except OperationalError as exc:
        raise HTTPException(
            status_code=503, detail="Task broker is unavailable"
        ) from exc
    return ImportTaskEnqueuedResponse(
        task_id=result.id, task_name=PUMPPRICE_MOBILE_IMPORT_TASK
    )


@router.get(
    "/import/pumpprice/mobile/tasks/{task_id}",
    response_model=ImportTaskStatusResponse,
    dependencies=[Depends(get_current_active_superuser)],
)
def get_import_pumpprice_mobile_task(task_id: str) -> ImportTaskStatusResponse:
    """Return the state (and result or error) of a background import task."""
    async_result = celery_app.AsyncResult(task_id)
    state = async_result.state
    payload: dict[str, Any] | None = None
    error: str | None = None
    if state == "SUCCESS" and isinstance(async_result.result, dict):
        payload = async_result.result
    elif state == "FAILURE":
        error = str(async_result.result)
    return ImportTaskStatusResponse(
        task_id=task_id, state=state, result=payload, error=error
    )
