"""Tests for the async PumpPrice mobile import endpoints."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.config import settings

BASE = f"{settings.API_V1_STR}/fuel/import/pumpprice/mobile"


def test_enqueue_returns_task_id(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    with patch("app.fuel.router.import_pumpprice_mobile_task") as task:
        task.delay.return_value = MagicMock(id="abc-123")
        response = client.post(f"{BASE}/async", headers=superuser_token_headers)

    assert response.status_code == 202
    assert response.json() == {
        "task_id": "abc-123",
        "task_name": "fuel.import_pumpprice_mobile",
    }


def test_enqueue_requires_superuser(client: TestClient) -> None:
    response = client.post(f"{BASE}/async")
    assert response.status_code in (401, 403)


def test_status_success(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    fake = MagicMock(state="SUCCESS", result={"status": "ok", "persisted_stations": 5})
    with patch("app.fuel.router.celery_app") as app:
        app.AsyncResult.return_value = fake
        response = client.get(f"{BASE}/tasks/abc", headers=superuser_token_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "SUCCESS"
    assert body["result"]["persisted_stations"] == 5
    assert body["error"] is None


def test_status_failure(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    fake = MagicMock(state="FAILURE", result=RuntimeError("boom"))
    with patch("app.fuel.router.celery_app") as app:
        app.AsyncResult.return_value = fake
        response = client.get(f"{BASE}/tasks/abc", headers=superuser_token_headers)

    assert response.json()["state"] == "FAILURE"
    assert response.json()["error"] == "boom"
