from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import UserRole
from tests.trip_plans.factories import create_user_with_role, headers_for

URL = "/api/v1/fuel-optimization/calculate"


def test_dispatcher_is_not_forbidden(client: TestClient, db: Session) -> None:
    user, password = create_user_with_role(db, UserRole.DISPATCHER)
    headers = headers_for(client, user, password)
    response = client.post(URL, headers=headers, json={})
    assert response.status_code == 422


def test_driver_is_forbidden(client: TestClient, db: Session) -> None:
    user, password = create_user_with_role(db, UserRole.DRIVER)
    headers = headers_for(client, user, password)
    response = client.post(URL, headers=headers, json={})
    assert response.status_code == 403
