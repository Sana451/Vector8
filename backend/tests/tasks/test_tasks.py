"""Tests for the Celery schedule registry and the PumpPrice import task."""

from unittest.mock import MagicMock, patch

import pytest

from app.fuel import tasks as fuel_tasks
from app.tasks import schedule
from app.tasks.base import _lock_key
from app.tasks.celery_app import celery_app


def test_schedule_empty_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(schedule.settings, "PUMPPRICE_MOBILE_SYNC_ENABLED", False)
    assert schedule.build_beat_schedule() == {}


def test_schedule_contains_import_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(schedule.settings, "PUMPPRICE_MOBILE_SYNC_ENABLED", True)
    entries = schedule.build_beat_schedule()
    assert [e["task"] for e in entries.values()] == [
        schedule.PUMPPRICE_MOBILE_IMPORT_TASK
    ]


def test_task_is_registered() -> None:
    assert schedule.PUMPPRICE_MOBILE_IMPORT_TASK in celery_app.tasks


def test_lock_key_is_stable_int32() -> None:
    key = _lock_key("fuel.import_pumpprice_mobile")
    assert key == _lock_key("fuel.import_pumpprice_mobile")
    assert -(2**31) <= key < 2**31


def test_task_skips_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fuel_tasks.settings, "PUMPPRICE_MOBILE_EMAIL", None)
    result = fuel_tasks.import_pumpprice_mobile.run()
    assert result == {"status": "skipped", "reason": "credentials_not_configured"}


def test_task_skips_when_lock_is_held(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fuel_tasks.settings, "PUMPPRICE_MOBILE_EMAIL", "a@b.c")
    monkeypatch.setattr(fuel_tasks.settings, "PUMPPRICE_MOBILE_PASSWORD", "pw")

    lock = MagicMock()
    lock.return_value.__enter__.return_value = False
    with patch.object(fuel_tasks, "advisory_lock", lock):
        result = fuel_tasks.import_pumpprice_mobile.run()

    assert result == {"status": "skipped", "reason": "already_running"}
