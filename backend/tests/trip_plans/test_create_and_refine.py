"""Creating and refining trip plans against a fake routing provider."""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.main import app
from app.models import UserRole
from app.routing.dependencies import get_routing_service
from app.routing.exceptions import RoutingNoRouteFoundError
from app.routing.schemas import CalculateRouteRequest, CalculateRouteResponse
from app.trip_plans.domain import TripPlanStatus
from tests.trip_plans.factories import (
    ROUTE_RESPONSE,
    create_optimization_run,
    create_optimization_stop,
    create_route,
    create_station,
    create_trip_plan,
    create_user_with_role,
    create_vehicle,
    headers_for,
)

PREFIX = f"{settings.API_V1_STR}/trip-plans"


class FakeRoutingService:
    provider_name = "here"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.requests: list[CalculateRouteRequest] = []
        self.force_refresh_flags: list[bool] = []
        self.error: Exception | None = None
        self.empty = False

    async def calculate_route(
        self, request: CalculateRouteRequest, *, force_refresh: bool = False
    ) -> CalculateRouteResponse:
        self.requests.append(request)
        self.force_refresh_flags.append(force_refresh)
        if self.error is not None:
            raise self.error
        if self.empty:
            return CalculateRouteResponse(id=None, routes=[])
        route = create_route(self.db, suffix="refined")
        return CalculateRouteResponse.model_validate({"id": route.id, **ROUTE_RESPONSE})


@pytest.fixture
def routing(db: Session) -> Generator[FakeRoutingService]:
    fake = FakeRoutingService(db)
    app.dependency_overrides[get_routing_service] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_routing_service, None)


def make_run(db: Session, *, with_stop: bool = True) -> uuid.UUID:
    base_route = create_route(db, suffix="base")
    vehicle = create_vehicle(db)
    run = create_optimization_run(db, route_id=base_route.id, vehicle_id=vehicle.id)
    if with_stop:
        station = create_station(db)
        create_optimization_stop(db, run_id=run.id, station_id=station.id)
    return run.id


class TestCreate:
    def test_refines_through_the_selected_stops(
        self, client: TestClient, db: Session, routing: FakeRoutingService
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        run_id = make_run(db)

        response = client.post(
            f"{PREFIX}/",
            headers=headers_for(client, dispatcher, password),
            json={"optimization_run_id": str(run_id)},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == TripPlanStatus.REFINED
        assert body["owner_id"] == str(dispatcher.id)
        assert body["refined_distance_meters"] == 1126540
        assert body["refined_provider"] == "here"
        assert body["refine_error"] is None
        assert body["refined_geometry"] is not None
        assert body["delta"]["distance_meters"] == 0
        assert [stop["label"] for stop in body["stops"]] == ["Love's #200"]

        waypoints = routing.requests[0].route_planning_locations.waypoints
        assert waypoints is not None
        assert [tuple(point) for point in waypoints.coordinates] == [(-93.5, 40.0)]

    def test_stop_duration_is_sent_in_seconds(
        self, client: TestClient, db: Session, routing: FakeRoutingService
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)

        client.post(
            f"{PREFIX}/",
            headers=headers_for(client, dispatcher, password),
            json={
                "optimization_run_id": str(make_run(db)),
                "stop_duration_minutes": 10,
            },
        )

        locations = routing.requests[0].route_planning_locations
        assert locations.waypoint_stop_duration_seconds == 600

    def test_custom_name_is_kept(
        self, client: TestClient, db: Session, routing: FakeRoutingService
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)

        response = client.post(
            f"{PREFIX}/",
            headers=headers_for(client, dispatcher, password),
            json={"optimization_run_id": str(make_run(db)), "name": "Friday load"},
        )

        assert response.json()["name"] == "Friday load"

    def test_provider_failure_keeps_the_trip_as_refine_failed(
        self, client: TestClient, db: Session, routing: FakeRoutingService
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        routing.error = RoutingNoRouteFoundError("no truck route")

        response = client.post(
            f"{PREFIX}/",
            headers=headers_for(client, dispatcher, password),
            json={"optimization_run_id": str(make_run(db))},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == TripPlanStatus.REFINE_FAILED
        assert "no truck route" in body["refine_error"]
        assert body["refined_route_id"] is None

    def test_empty_provider_answer_counts_as_failure(
        self, client: TestClient, db: Session, routing: FakeRoutingService
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        routing.empty = True

        body = client.post(
            f"{PREFIX}/",
            headers=headers_for(client, dispatcher, password),
            json={"optimization_run_id": str(make_run(db))},
        ).json()

        assert body["status"] == TripPlanStatus.REFINE_FAILED
        assert body["refine_error"]

    def test_unknown_optimization_run_is_not_found(
        self, client: TestClient, db: Session, routing: FakeRoutingService
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)

        response = client.post(
            f"{PREFIX}/",
            headers=headers_for(client, dispatcher, password),
            json={"optimization_run_id": str(uuid.uuid4())},
        )

        assert response.status_code == 404
        assert routing.requests == []

    def test_unknown_provider_is_a_bad_request(
        self, client: TestClient, db: Session, routing: FakeRoutingService
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)

        response = client.post(
            f"{PREFIX}/",
            headers=headers_for(client, dispatcher, password),
            json={
                "optimization_run_id": str(make_run(db)),
                "provider": "no-such-provider",
            },
        )

        assert response.status_code == 400

    def test_driver_cannot_create(
        self, client: TestClient, db: Session, routing: FakeRoutingService
    ) -> None:
        driver, password = create_user_with_role(db, UserRole.DRIVER)

        response = client.post(
            f"{PREFIX}/",
            headers=headers_for(client, driver, password),
            json={"optimization_run_id": str(make_run(db))},
        )

        assert response.status_code == 403

    def test_requires_authentication(self, client: TestClient) -> None:
        response = client.post(
            f"{PREFIX}/", json={"optimization_run_id": str(uuid.uuid4())}
        )

        assert response.status_code == 401


class TestRefine:
    def test_recovers_a_failed_trip(
        self, client: TestClient, db: Session, routing: FakeRoutingService
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        headers = headers_for(client, dispatcher, password)
        routing.error = RoutingNoRouteFoundError("no truck route")
        created = client.post(
            f"{PREFIX}/",
            headers=headers,
            json={"optimization_run_id": str(make_run(db))},
        ).json()
        routing.error = None

        response = client.post(
            f"{PREFIX}/{created['id']}/refine",
            headers=headers,
            json={"force_refresh": True},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == TripPlanStatus.REFINED
        assert body["refine_error"] is None
        assert routing.force_refresh_flags[-1] is True

    def test_run_without_stops_is_a_bad_request(
        self, client: TestClient, db: Session, routing: FakeRoutingService
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        trip = create_trip_plan(db, owner=dispatcher, refined=False)

        response = client.post(
            f"{PREFIX}/{trip.id}/refine",
            headers=headers_for(client, dispatcher, password),
            json={},
        )

        assert response.status_code == 400
        assert routing.requests == []

    def test_other_dispatcher_cannot_refine(
        self, client: TestClient, db: Session, routing: FakeRoutingService
    ) -> None:
        owner, _ = create_user_with_role(db, UserRole.DISPATCHER)
        other, password = create_user_with_role(db, UserRole.DISPATCHER)
        trip = create_trip_plan(db, owner=owner)

        response = client.post(
            f"{PREFIX}/{trip.id}/refine",
            headers=headers_for(client, other, password),
            json={},
        )

        assert response.status_code == 403
        assert routing.requests == []

    def test_unknown_trip_is_not_found(
        self, client: TestClient, db: Session, routing: FakeRoutingService
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)

        response = client.post(
            f"{PREFIX}/{uuid.uuid4()}/refine",
            headers=headers_for(client, dispatcher, password),
            json={},
        )

        assert response.status_code == 404
