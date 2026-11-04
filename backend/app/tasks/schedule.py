"""Central registry of periodic (celery beat) tasks.

To schedule a new task, add one entry to ``build_beat_schedule``.
"""

from typing import Any

from celery.schedules import crontab

from app.core.config import settings

PUMPPRICE_MOBILE_IMPORT_TASK = "fuel.import_pumpprice_mobile"


def build_beat_schedule() -> dict[str, dict[str, Any]]:
    """Return the beat schedule, including only the enabled tasks."""
    schedule: dict[str, dict[str, Any]] = {}

    if settings.PUMPPRICE_MOBILE_SYNC_ENABLED:
        schedule["fuel-import-pumpprice-mobile"] = {
            "task": PUMPPRICE_MOBILE_IMPORT_TASK,
            "schedule": crontab(
                minute=settings.PUMPPRICE_MOBILE_SYNC_CRON_MINUTE,
                hour=settings.PUMPPRICE_MOBILE_SYNC_CRON_HOUR,
            ),
        }

    return schedule
