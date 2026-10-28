"""Driver endpoints and role gating."""

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import User, UserCreate, UserRole
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string

PREFIX = f"{settings.API_V1_STR}/drivers"


def create_user_with_role(db: Session, role: UserRole) -> tuple[User, str]:
    password = random_lower_string()
    user = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=password, role=role),
    )
    return user, password


def headers_for(client: TestClient, user: User, password: str) -> dict[str, str]:
    return user_authentication_headers(
        client=client, email=user.email, password=password
    )


class TestDriverListing:
    def test_dispatcher_sees_only_drivers(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        driver, _ = create_user_with_role(db, UserRole.DRIVER)

        response = client.get(
            f"{PREFIX}/", headers=headers_for(client, dispatcher, password)
        )

        assert response.status_code == 200
        ids = {item["id"] for item in response.json()["data"]}
        assert str(driver.id) in ids
        assert str(dispatcher.id) not in ids

    def test_driver_cannot_list_drivers(self, client: TestClient, db: Session) -> None:
        driver, password = create_user_with_role(db, UserRole.DRIVER)

        response = client.get(
            f"{PREFIX}/", headers=headers_for(client, driver, password)
        )

        assert response.status_code == 403

    def test_superuser_can_list_drivers(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        response = client.get(f"{PREFIX}/", headers=superuser_token_headers)

        assert response.status_code == 200


class TestDriverProfile:
    def test_own_profile_starts_empty_and_can_be_updated(
        self, client: TestClient, db: Session
    ) -> None:
        driver, password = create_user_with_role(db, UserRole.DRIVER)
        headers = headers_for(client, driver, password)

        empty = client.get(f"{PREFIX}/me/profile", headers=headers)
        assert empty.status_code == 200
        assert empty.json()["phone"] is None

        updated = client.put(
            f"{PREFIX}/me/profile",
            headers=headers,
            json={"phone": "+15550001111", "license_number": "TX-4412"},
        )
        assert updated.status_code == 200
        assert updated.json()["phone"] == "+15550001111"
        assert updated.json()["license_number"] == "TX-4412"

    def test_dispatcher_cannot_read_own_driver_profile(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)

        response = client.get(
            f"{PREFIX}/me/profile", headers=headers_for(client, dispatcher, password)
        )

        assert response.status_code == 403

    def test_dispatcher_updates_driver_profile(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        driver, _ = create_user_with_role(db, UserRole.DRIVER)

        response = client.put(
            f"{PREFIX}/{driver.id}/profile",
            headers=headers_for(client, dispatcher, password),
            json={"notes": "Prefers night runs"},
        )

        assert response.status_code == 200
        assert response.json()["profile"]["notes"] == "Prefers night runs"

    def test_non_driver_user_id_is_not_found(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        other, _ = create_user_with_role(db, UserRole.DISPATCHER)
        headers = headers_for(client, dispatcher, password)

        assert client.get(f"{PREFIX}/{other.id}", headers=headers).status_code == 404
        assert (
            client.get(f"{PREFIX}/{uuid.uuid4()}", headers=headers).status_code == 404
        )
