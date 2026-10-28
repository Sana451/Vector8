"""Trip plan endpoints: role gating, assignment, status, export and sharing."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import UserRole
from app.trip_plans.domain import TripPlanStatus
from tests.trip_plans.factories import (
    create_trip_plan,
    create_user_with_role,
    headers_for,
)

PREFIX = f"{settings.API_V1_STR}/trip-plans"


class TestReadTripPlan:
    def test_owner_dispatcher_sees_the_trip(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        trip = create_trip_plan(db, owner=dispatcher)

        response = client.get(
            f"{PREFIX}/{trip.id}", headers=headers_for(client, dispatcher, password)
        )

        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Dallas run"
        assert len(body["stops"]) == 3
        assert body["refined_geometry"] is not None

    def test_detail_reports_the_delta_against_the_base_route(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        trip = create_trip_plan(db, owner=dispatcher)

        response = client.get(
            f"{PREFIX}/{trip.id}", headers=headers_for(client, dispatcher, password)
        )

        assert response.json()["delta"] == {
            "distance_meters": 1130000 - 1126540,
            "duration_seconds": 36600 - 36000,
        }

    def test_another_dispatcher_is_refused(
        self, client: TestClient, db: Session
    ) -> None:
        owner, _ = create_user_with_role(db, UserRole.DISPATCHER)
        other, password = create_user_with_role(db, UserRole.DISPATCHER)
        trip = create_trip_plan(db, owner=owner)

        response = client.get(
            f"{PREFIX}/{trip.id}", headers=headers_for(client, other, password)
        )

        assert response.status_code == 403

    def test_assigned_driver_sees_the_trip(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, _ = create_user_with_role(db, UserRole.DISPATCHER)
        driver, password = create_user_with_role(db, UserRole.DRIVER)
        trip = create_trip_plan(db, owner=dispatcher, assigned_driver=driver)

        response = client.get(
            f"{PREFIX}/{trip.id}", headers=headers_for(client, driver, password)
        )

        assert response.status_code == 200

    def test_unassigned_driver_is_refused(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, _ = create_user_with_role(db, UserRole.DISPATCHER)
        driver, password = create_user_with_role(db, UserRole.DRIVER)
        trip = create_trip_plan(db, owner=dispatcher)

        response = client.get(
            f"{PREFIX}/{trip.id}", headers=headers_for(client, driver, password)
        )

        assert response.status_code == 403

    def test_unknown_trip_is_not_found(self, client: TestClient, db: Session) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)

        response = client.get(
            f"{PREFIX}/{uuid.uuid4()}",
            headers=headers_for(client, dispatcher, password),
        )

        assert response.status_code == 404

    def test_anonymous_access_is_rejected(self, client: TestClient) -> None:
        response = client.get(f"{PREFIX}/{uuid.uuid4()}")

        assert response.status_code == 401


class TestListTripPlans:
    def test_dispatcher_sees_only_own_trips(
        self, client: TestClient, db: Session
    ) -> None:
        owner, password = create_user_with_role(db, UserRole.DISPATCHER)
        other, _ = create_user_with_role(db, UserRole.DISPATCHER)
        mine = create_trip_plan(db, owner=owner)
        theirs = create_trip_plan(db, owner=other)

        response = client.get(
            f"{PREFIX}/", headers=headers_for(client, owner, password)
        )

        ids = {item["id"] for item in response.json()["data"]}
        assert str(mine.id) in ids
        assert str(theirs.id) not in ids

    def test_driver_cannot_list_dispatcher_trips(
        self, client: TestClient, db: Session
    ) -> None:
        driver, password = create_user_with_role(db, UserRole.DRIVER)

        response = client.get(
            f"{PREFIX}/", headers=headers_for(client, driver, password)
        )

        assert response.status_code == 403

    def test_driver_lists_only_assigned_trips(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, _ = create_user_with_role(db, UserRole.DISPATCHER)
        driver, password = create_user_with_role(db, UserRole.DRIVER)
        assigned = create_trip_plan(db, owner=dispatcher, assigned_driver=driver)
        unassigned = create_trip_plan(db, owner=dispatcher)

        response = client.get(
            f"{PREFIX}/my", headers=headers_for(client, driver, password)
        )

        ids = {item["id"] for item in response.json()["data"]}
        assert ids == {str(assigned.id)}
        assert str(unassigned.id) not in ids

    def test_dispatcher_cannot_use_the_driver_list(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)

        response = client.get(
            f"{PREFIX}/my", headers=headers_for(client, dispatcher, password)
        )

        assert response.status_code == 403


class TestAssignment:
    def test_assigning_a_driver_moves_the_trip_to_assigned(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        driver, _ = create_user_with_role(db, UserRole.DRIVER)
        trip = create_trip_plan(db, owner=dispatcher)

        response = client.post(
            f"{PREFIX}/{trip.id}/assign",
            headers=headers_for(client, dispatcher, password),
            json={"driver_id": str(driver.id)},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["assigned_driver_id"] == str(driver.id)
        assert body["status"] == TripPlanStatus.ASSIGNED

    def test_unassigning_rolls_the_status_back(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        driver, _ = create_user_with_role(db, UserRole.DRIVER)
        trip = create_trip_plan(
            db,
            owner=dispatcher,
            assigned_driver=driver,
            status=TripPlanStatus.ASSIGNED,
        )

        response = client.post(
            f"{PREFIX}/{trip.id}/assign",
            headers=headers_for(client, dispatcher, password),
            json={"driver_id": None},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["assigned_driver_id"] is None
        assert body["status"] == TripPlanStatus.REFINED

    def test_assigning_a_non_driver_is_rejected(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        other, _ = create_user_with_role(db, UserRole.DISPATCHER)
        trip = create_trip_plan(db, owner=dispatcher)

        response = client.post(
            f"{PREFIX}/{trip.id}/assign",
            headers=headers_for(client, dispatcher, password),
            json={"driver_id": str(other.id)},
        )

        assert response.status_code == 404

    def test_driver_cannot_assign(self, client: TestClient, db: Session) -> None:
        dispatcher, _ = create_user_with_role(db, UserRole.DISPATCHER)
        driver, password = create_user_with_role(db, UserRole.DRIVER)
        trip = create_trip_plan(db, owner=dispatcher, assigned_driver=driver)

        response = client.post(
            f"{PREFIX}/{trip.id}/assign",
            headers=headers_for(client, driver, password),
            json={"driver_id": str(driver.id)},
        )

        assert response.status_code == 403


class TestStatusUpdates:
    def test_driver_starts_and_completes_the_trip(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, _ = create_user_with_role(db, UserRole.DISPATCHER)
        driver, password = create_user_with_role(db, UserRole.DRIVER)
        trip = create_trip_plan(
            db,
            owner=dispatcher,
            assigned_driver=driver,
            status=TripPlanStatus.ASSIGNED,
        )
        headers = headers_for(client, driver, password)

        started = client.patch(
            f"{PREFIX}/{trip.id}/status",
            headers=headers,
            json={"status": TripPlanStatus.IN_PROGRESS},
        )
        completed = client.patch(
            f"{PREFIX}/{trip.id}/status",
            headers=headers,
            json={"status": TripPlanStatus.COMPLETED},
        )

        assert started.json()["status"] == TripPlanStatus.IN_PROGRESS
        assert completed.json()["status"] == TripPlanStatus.COMPLETED

    def test_driver_cannot_cancel_the_trip(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, _ = create_user_with_role(db, UserRole.DISPATCHER)
        driver, password = create_user_with_role(db, UserRole.DRIVER)
        trip = create_trip_plan(
            db,
            owner=dispatcher,
            assigned_driver=driver,
            status=TripPlanStatus.ASSIGNED,
        )

        response = client.patch(
            f"{PREFIX}/{trip.id}/status",
            headers=headers_for(client, driver, password),
            json={"status": TripPlanStatus.CANCELLED},
        )

        assert response.status_code == 400

    def test_dispatcher_can_cancel_the_trip(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        trip = create_trip_plan(db, owner=dispatcher)

        response = client.patch(
            f"{PREFIX}/{trip.id}/status",
            headers=headers_for(client, dispatcher, password),
            json={"status": TripPlanStatus.CANCELLED},
        )

        assert response.json()["status"] == TripPlanStatus.CANCELLED

    def test_nobody_can_rewind_to_draft(self, client: TestClient, db: Session) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        trip = create_trip_plan(db, owner=dispatcher)

        response = client.patch(
            f"{PREFIX}/{trip.id}/status",
            headers=headers_for(client, dispatcher, password),
            json={"status": TripPlanStatus.DRAFT},
        )

        assert response.status_code == 400


class TestExportEndpoints:
    def test_gpx_is_returned_as_an_attachment(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        trip = create_trip_plan(db, owner=dispatcher)

        response = client.get(
            f"{PREFIX}/{trip.id}/export.gpx",
            headers=headers_for(client, dispatcher, password),
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/gpx+xml")
        assert "attachment" in response.headers["content-disposition"]
        assert "Dallas-run.gpx" in response.headers["content-disposition"]
        assert "<trkpt" in response.text

    def test_kml_contains_the_route_line(self, client: TestClient, db: Session) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        trip = create_trip_plan(db, owner=dispatcher)

        response = client.get(
            f"{PREFIX}/{trip.id}/export.kml",
            headers=headers_for(client, dispatcher, password),
        )

        assert response.status_code == 200
        assert "<LineString" in response.text

    def test_csv_lists_every_stop(self, client: TestClient, db: Session) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        trip = create_trip_plan(db, owner=dispatcher)

        response = client.get(
            f"{PREFIX}/{trip.id}/export.csv",
            headers=headers_for(client, dispatcher, password),
        )

        assert response.status_code == 200
        lines = response.text.strip().splitlines()
        assert lines[0].startswith("sequence,kind,label")
        assert len(lines) == 4

    def test_assigned_driver_can_export(self, client: TestClient, db: Session) -> None:
        dispatcher, _ = create_user_with_role(db, UserRole.DISPATCHER)
        driver, password = create_user_with_role(db, UserRole.DRIVER)
        trip = create_trip_plan(db, owner=dispatcher, assigned_driver=driver)

        response = client.get(
            f"{PREFIX}/{trip.id}/export.gpx",
            headers=headers_for(client, driver, password),
        )

        assert response.status_code == 200

    def test_unassigned_driver_cannot_export(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, _ = create_user_with_role(db, UserRole.DISPATCHER)
        driver, password = create_user_with_role(db, UserRole.DRIVER)
        trip = create_trip_plan(db, owner=dispatcher)

        response = client.get(
            f"{PREFIX}/{trip.id}/export.gpx",
            headers=headers_for(client, driver, password),
        )

        assert response.status_code == 403

    def test_unknown_format_is_rejected(self, client: TestClient, db: Session) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        trip = create_trip_plan(db, owner=dispatcher)

        response = client.get(
            f"{PREFIX}/{trip.id}/export.pdf",
            headers=headers_for(client, dispatcher, password),
        )

        assert response.status_code == 422

    def test_export_falls_back_to_the_base_route(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        trip = create_trip_plan(
            db, owner=dispatcher, refined=False, status=TripPlanStatus.DRAFT
        )

        response = client.get(
            f"{PREFIX}/{trip.id}/export.gpx",
            headers=headers_for(client, dispatcher, password),
        )

        assert response.status_code == 200
        assert "<trkpt" in response.text


class TestDeletion:
    def test_owner_can_delete(self, client: TestClient, db: Session) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        trip = create_trip_plan(db, owner=dispatcher)
        headers = headers_for(client, dispatcher, password)

        deleted = client.delete(f"{PREFIX}/{trip.id}", headers=headers)
        missing = client.get(f"{PREFIX}/{trip.id}", headers=headers)

        assert deleted.status_code == 204
        assert missing.status_code == 404

    def test_driver_cannot_delete(self, client: TestClient, db: Session) -> None:
        dispatcher, _ = create_user_with_role(db, UserRole.DISPATCHER)
        driver, password = create_user_with_role(db, UserRole.DRIVER)
        trip = create_trip_plan(db, owner=dispatcher, assigned_driver=driver)

        response = client.delete(
            f"{PREFIX}/{trip.id}", headers=headers_for(client, driver, password)
        )

        assert response.status_code == 403


class TestSharing:
    def test_owner_issues_a_token_that_works_without_login(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        trip = create_trip_plan(db, owner=dispatcher)

        issued = client.post(
            f"{PREFIX}/{trip.id}/share",
            headers=headers_for(client, dispatcher, password),
            json={"enabled": True},
        )
        token = issued.json()["share_token"]
        shared = client.get(f"{PREFIX}/shared/{token}")

        assert issued.status_code == 200
        assert len(token) >= 40
        assert shared.status_code == 200
        body = shared.json()
        assert body["name"] == "Dallas run"
        assert len(body["stops"]) == 3
        assert body["geometry"] is not None

    def test_shared_view_leaks_no_identifiers(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, _ = create_user_with_role(db, UserRole.DISPATCHER)
        create_trip_plan(db, owner=dispatcher, share_token="public-token")

        body = client.get(f"{PREFIX}/shared/public-token").json()

        assert "id" not in body
        assert "owner_id" not in body
        assert "assigned_driver_id" not in body
        assert "share_token" not in body

    def test_detail_reports_shared_flag_without_the_token(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        trip = create_trip_plan(db, owner=dispatcher, share_token="flag-token")

        body = client.get(
            f"{PREFIX}/{trip.id}", headers=headers_for(client, dispatcher, password)
        ).json()

        assert body["is_shared"] is True
        assert "share_token" not in body

    def test_reissuing_keeps_the_same_token(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        trip = create_trip_plan(db, owner=dispatcher)
        headers = headers_for(client, dispatcher, password)

        first = client.post(
            f"{PREFIX}/{trip.id}/share", headers=headers, json={"enabled": True}
        )
        second = client.post(
            f"{PREFIX}/{trip.id}/share", headers=headers, json={"enabled": True}
        )

        assert first.json()["share_token"] == second.json()["share_token"]

    def test_revoked_token_stops_working(self, client: TestClient, db: Session) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        trip = create_trip_plan(db, owner=dispatcher, share_token="revoke-me")
        headers = headers_for(client, dispatcher, password)

        revoked = client.post(
            f"{PREFIX}/{trip.id}/share", headers=headers, json={"enabled": False}
        )
        after = client.get(f"{PREFIX}/shared/revoke-me")

        assert revoked.json()["share_token"] is None
        assert after.status_code == 404

    def test_unknown_token_is_not_found(self, client: TestClient) -> None:
        assert client.get(f"{PREFIX}/shared/nope").status_code == 404

    def test_driver_cannot_share(self, client: TestClient, db: Session) -> None:
        dispatcher, _ = create_user_with_role(db, UserRole.DISPATCHER)
        driver, password = create_user_with_role(db, UserRole.DRIVER)
        trip = create_trip_plan(db, owner=dispatcher, assigned_driver=driver)

        response = client.post(
            f"{PREFIX}/{trip.id}/share",
            headers=headers_for(client, driver, password),
            json={"enabled": True},
        )

        assert response.status_code == 403

    def test_other_dispatcher_cannot_share(
        self, client: TestClient, db: Session
    ) -> None:
        owner, _ = create_user_with_role(db, UserRole.DISPATCHER)
        other, password = create_user_with_role(db, UserRole.DISPATCHER)
        trip = create_trip_plan(db, owner=owner)

        response = client.post(
            f"{PREFIX}/{trip.id}/share",
            headers=headers_for(client, other, password),
            json={"enabled": True},
        )

        assert response.status_code == 403
