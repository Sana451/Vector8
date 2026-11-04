"""Celery application.

Run worker: ``celery -A app.tasks.celery_app worker -l info``
Run beat:   ``celery -A app.tasks.celery_app beat -l info``
Run flower: ``celery -A app.tasks.celery_app flower``
"""

from celery import Celery

from app.core.config import settings
from app.core.logging import configure_logging
from app.tasks.schedule import build_beat_schedule

# Modules that define tasks. Add new task modules here.
TASK_MODULES = ["app.fuel.tasks"]

configure_logging(settings.FASTAPI_ENV)

celery_app = Celery(
    "vector8",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=TASK_MODULES,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=settings.CELERY_TIMEZONE,
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT_SECONDS,
    task_soft_time_limit=settings.CELERY_TASK_TIME_LIMIT_SECONDS - 60,
    task_track_started=True,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    result_expires=settings.CELERY_RESULT_EXPIRES_SECONDS,
    worker_prefetch_multiplier=1,
    worker_hijack_root_logger=False,
    broker_connection_retry_on_startup=True,
    beat_schedule=build_beat_schedule(),
)
