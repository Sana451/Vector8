"""Shared building blocks for Celery tasks."""

import zlib
from collections.abc import Iterator
from contextlib import contextmanager

from celery import Task
from sqlalchemy import text

from app.core.db import engine
from app.core.logging import get_logger

logger = get_logger(__name__)


class VectorTask(Task):  # type: ignore[misc]
    """Base class for all project tasks: logs lifecycle events."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):  # type: ignore[no-untyped-def]
        logger.error(
            "Task failed",
            task=self.name,
            task_id=task_id,
            error=str(exc),
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):  # type: ignore[no-untyped-def]
        logger.warning(
            "Task retry",
            task=self.name,
            task_id=task_id,
            error=str(exc),
        )

    def on_success(self, retval, task_id, args, kwargs):  # type: ignore[no-untyped-def]
        logger.info("Task succeeded", task=self.name, task_id=task_id)


def _lock_key(name: str) -> int:
    """Stable signed 32-bit key for a PostgreSQL advisory lock."""
    return zlib.crc32(name.encode()) - 2**31


@contextmanager
def advisory_lock(name: str) -> Iterator[bool]:
    """Try to take a PostgreSQL advisory lock; yields whether it was acquired.

    The lock is held on a dedicated autocommit connection for the duration of
    the block, so concurrent runs of the same job (beat + manual, several
    workers) never overlap.
    """
    key = _lock_key(name)
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        acquired = bool(
            conn.execute(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
            ).scalar()
        )
        try:
            yield acquired
        finally:
            if acquired:
                conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
