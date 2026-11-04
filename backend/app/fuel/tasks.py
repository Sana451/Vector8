"""Celery tasks for fuel data."""

from typing import Any

from sqlmodel import Session

from app.core.config import settings
from app.core.db import engine
from app.core.logging import get_logger
from app.fuel.service import PumpPriceImportService
from app.map.repository import FuelStationRepository
from app.providers.exceptions import ProviderAuthenticationError, ProviderError
from app.tasks.base import VectorTask, advisory_lock
from app.tasks.celery_app import celery_app
from app.tasks.runner import run_async
from app.tasks.schedule import PUMPPRICE_MOBILE_IMPORT_TASK

logger = get_logger(__name__)


@celery_app.task(
    name=PUMPPRICE_MOBILE_IMPORT_TASK,
    base=VectorTask,
    autoretry_for=(ProviderError,),
    dont_autoretry_for=(ProviderAuthenticationError,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def import_pumpprice_mobile() -> dict[str, Any]:
    """Import PumpPrice fuel prices via the mobile API (same logic as the endpoint)."""
    if not settings.PUMPPRICE_MOBILE_EMAIL or not settings.PUMPPRICE_MOBILE_PASSWORD:
        logger.warning("PumpPrice mobile credentials are not configured, skipping")
        return {"status": "skipped", "reason": "credentials_not_configured"}

    with advisory_lock(PUMPPRICE_MOBILE_IMPORT_TASK) as acquired:
        if not acquired:
            logger.warning("PumpPrice mobile import is already running, skipping")
            return {"status": "skipped", "reason": "already_running"}

        with Session(engine) as session:
            service = PumpPriceImportService(FuelStationRepository(session))
            result = run_async(service.import_prices_mobile())

    return {"status": "ok", **result.model_dump(mode="json")}
