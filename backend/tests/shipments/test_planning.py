"""Planning a trip from a shipment, end to end against fake providers."""

from __future__ import annotations

from collections.abc import Generator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlmodel import Session

from app.core.config import settings
from app.fleet.positions import VehiclePosition
from app.fuel_optimization.dependencies import get_optimize_fuel_use_case
from app.main import app
from app.routing.dependencies import get_routing_service
from app.routing.exceptions import RoutingError, RoutingNoRouteFoundError
from app.routing.schemas import CalculateRouteRequest, CalculateRouteResponse
from app.shipments.domain import PlanningStatus
from tests.shipments.conftest import (
    FakeGeocodingProvider,
    FakeLLMProvider,
    create_dispatcher,
    headers_for,
)
from tests.shipments.test_router import upload
from tests.trip_plans.factories import (
    ROUTE_RESPONSE,
    create_optimization_run,
    create_optimization_stop,
    create_route,
    create_station,
    create_vehicle,
)

SHIPMENTS = f"{settings.API_V1_STR}/shipments"
VEHICLES = f"{settings.API_V1_STR}/vehicles"
TRIPS = f"{settings.API_V1_STR}/trip-plans"


class FakeRoutingService:
    provider_name = "here"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.requests: list[CalculateRouteRequest] = []
        self.error: Exception | None = None

    async def calculate_route(
        self, request: CalculateRouteRequest, *, force_refresh: bool = False
    ) -> CalculateRouteResponse:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        route = create_route(self.db, suffix="planned")
        return CalculateRouteResponse.model_validate({"id": route.id, **ROUTE_RESPONSE})


class FakeOptimizer:
    def __init__(self, db: Session, vehicle_id: Any) -> None:
        self.db = db
        self.vehicle_id = vehicle_id

    def execute(self, request: Any) -> Any:
        run = create_optimization_run(
            self.db, route_id=request.route_id, vehicle_id=self.vehicle_id
        )
        create_optimization_stop(
            self.db, run_id=run.id, station_id=create_station(self.db).id
        )
        return SimpleNamespace(optimization_run_id=run.id)


@pytest.fixture
def routing(db: Session) -> Generator[FakeRoutingService]:
    fake = FakeRoutingService(db)
    app.dependency_overrides[get_routing_service] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_routing_service, None)


@pytest.fixture
def shipment_setup(
    client: TestClient,
    db: Session,
    sample_pdf: bytes,
    fake_llm: FakeLLMProvider,  # noqa: ARG001
    fake_geocoder: FakeGeocodingProvider,  # noqa: ARG001
    routing: FakeRoutingService,  # noqa: ARG001
) -> Generator[tuple[dict[str, str], str, Any]]:
    user, password = create_dispatcher(db)
    headers = headers_for(client, user, password)
    shipment_id = upload(client, headers, sample_pdf).json()["shipment"]["id"]
    vehicle = create_vehicle(db)
    app.dependency_overrides[get_optimize_fuel_use_case] = lambda: FakeOptimizer(
        db, vehicle.id
    )
    yield headers, shipment_id, vehicle
    app.dependency_overrides.pop(get_optimize_fuel_use_case, None)


def record_position(
    client: TestClient, headers: dict[str, str], vehicle_id: Any, lon: float, lat: float
) -> None:
    response = client.post(
        f"{VEHICLES}/{vehicle_id}/position",
        headers=headers,
        json={"longitude": lon, "latitude": lat, "label": "Yard"},
    )
    assert response.status_code == 201, response.text


class TestVehiclePositions:
    def test_latest_position_wins(
        self, client: TestClient, shipment_setup: tuple[dict[str, str], str, Any]
    ) -> None:
        headers, _, vehicle = shipment_setup
        record_position(client, headers, vehicle.id, -90.0, 35.0)
        record_position(client, headers, vehicle.id, -91.0, 36.0)

        response = client.get(f"{VEHICLES}/{vehicle.id}/position", headers=headers)

        assert response.status_code == 200
        assert response.json()["longitude"] == -91.0
        assert response.json()["source"] == "manual"

    def test_missing_position_is_404(
        self, client: TestClient, shipment_setup: tuple[dict[str, str], str, Any]
    ) -> None:
        headers, _, vehicle = shipment_setup

        response = client.get(f"{VEHICLES}/{vehicle.id}/position", headers=headers)

        assert response.status_code == 404


class TestVehicleSuggestions:
    def test_nearest_vehicle_first_and_unlocated_last(
        self,
        client: TestClient,
        db: Session,
        shipment_setup: tuple[dict[str, str], str, Any],
    ) -> None:
        headers, shipment_id, near = shipment_setup
        far = create_vehicle(db)
        unlocated = create_vehicle(db)
        # The fake geocoder puts the pickup near (-83.46, 42.49).
        record_position(client, headers, near.id, -83.5, 42.5)
        record_position(client, headers, far.id, -120.0, 35.0)

        response = client.get(
            f"{SHIPMENTS}/{shipment_id}/vehicle-suggestions", headers=headers
        )

        assert response.status_code == 200
        data = response.json()["data"]
        ids = [row["vehicle_id"] for row in data]
        assert ids.index(str(near.id)) < ids.index(str(far.id))
        located = [row for row in data if row["distance_to_pickup_meters"] is not None]
        assert data[: len(located)] == located
        assert str(unlocated.id) in ids[len(located) :]
        assert data[0]["distance_to_pickup_meters"] < 10_000
        assert data[-1]["distance_to_pickup_meters"] is None
        assert data[0]["is_position_stale"] is False


class TestPlan:
    def test_routes_through_the_pickup_and_marks_planned(
        self,
        client: TestClient,
        routing: FakeRoutingService,
        shipment_setup: tuple[dict[str, str], str, Any],
    ) -> None:
        headers, shipment_id, vehicle = shipment_setup
        record_position(client, headers, vehicle.id, -83.5, 42.5)

        response = client.post(
            f"{SHIPMENTS}/{shipment_id}/plan",
            headers=headers,
            json={"vehicle_id": str(vehicle.id), "initial_fuel_gallons": "80"},
        )

        assert response.status_code == 201, response.text
        trip = response.json()
        kinds = [stop["kind"] for stop in trip["stops"]]
        assert kinds == ["start", "refuel", "pickup", "destination"]
        assert [stop["sequence"] for stop in trip["stops"][1:3]] == [1, 2]

        first = routing.requests[0].route_planning_locations
        assert first.origin.coordinates == (-83.5, 42.5)
        assert len(first.waypoints.coordinates) == 1
        refined = routing.requests[1].route_planning_locations
        assert len(refined.waypoints.coordinates) == 2

        shipment = client.get(f"{SHIPMENTS}/{shipment_id}", headers=headers).json()
        assert shipment["planning_status"] == PlanningStatus.PLANNED

    def test_deleting_the_trip_reopens_the_shipment(
        self,
        client: TestClient,
        shipment_setup: tuple[dict[str, str], str, Any],
    ) -> None:
        headers, shipment_id, vehicle = shipment_setup
        trip = client.post(
            f"{SHIPMENTS}/{shipment_id}/plan",
            headers=headers,
            json={
                "vehicle_id": str(vehicle.id),
                "initial_fuel_gallons": "80",
                "origin": [-83.5, 42.5],
            },
        ).json()

        assert (
            client.delete(f"{TRIPS}/{trip['id']}", headers=headers).status_code == 204
        )

        shipment = client.get(f"{SHIPMENTS}/{shipment_id}", headers=headers).json()
        assert shipment["planning_status"] == PlanningStatus.UNPLANNED

    def test_needs_an_origin_when_the_vehicle_has_no_position(
        self,
        client: TestClient,
        shipment_setup: tuple[dict[str, str], str, Any],
    ) -> None:
        headers, shipment_id, vehicle = shipment_setup

        response = client.post(
            f"{SHIPMENTS}/{shipment_id}/plan",
            headers=headers,
            json={"vehicle_id": str(vehicle.id), "initial_fuel_gallons": "80"},
        )

        assert response.status_code == 422
        assert "position" in response.json()["detail"]

    def test_no_route_found_is_a_422_and_leaves_shipment_unplanned(
        self,
        client: TestClient,
        routing: FakeRoutingService,
        shipment_setup: tuple[dict[str, str], str, Any],
    ) -> None:
        headers, shipment_id, vehicle = shipment_setup
        routing.error = RoutingNoRouteFoundError("no route")

        response = client.post(
            f"{SHIPMENTS}/{shipment_id}/plan",
            headers=headers,
            json={
                "vehicle_id": str(vehicle.id),
                "initial_fuel_gallons": "80",
                "origin": [-83.5, 42.5],
            },
        )

        assert response.status_code == 422
        shipment = client.get(f"{SHIPMENTS}/{shipment_id}", headers=headers).json()
        assert shipment["planning_status"] == PlanningStatus.UNPLANNED

    def test_provider_outage_is_a_502(
        self,
        client: TestClient,
        routing: FakeRoutingService,
        shipment_setup: tuple[dict[str, str], str, Any],
    ) -> None:
        headers, shipment_id, vehicle = shipment_setup
        routing.error = RoutingError("provider timeout")

        response = client.post(
            f"{SHIPMENTS}/{shipment_id}/plan",
            headers=headers,
            json={
                "vehicle_id": str(vehicle.id),
                "initial_fuel_gallons": "80",
                "origin": [-83.5, 42.5],
            },
        )

        assert response.status_code == 502

    def test_unknown_vehicle_is_404(
        self,
        client: TestClient,
        shipment_setup: tuple[dict[str, str], str, Any],
    ) -> None:
        headers, shipment_id, _ = shipment_setup

        response = client.post(
            f"{SHIPMENTS}/{shipment_id}/plan",
            headers=headers,
            json={
                "vehicle_id": "00000000-0000-0000-0000-000000000000",
                "initial_fuel_gallons": "80",
                "origin": [-83.5, 42.5],
            },
        )

        assert response.status_code == 404


def plan_shipment(
    client: TestClient,
    headers: dict[str, str],
    shipment_id: str,
    vehicle_id: Any,
) -> dict[str, Any]:
    response = client.post(
        f"{SHIPMENTS}/{shipment_id}/plan",
        headers=headers,
        json={
            "vehicle_id": str(vehicle_id),
            "initial_fuel_gallons": "80",
            "origin": [-83.5, 42.5],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestCompletedTrip:
    def test_completing_the_trip_completes_shipment_and_records_position(
        self,
        client: TestClient,
        shipment_setup: tuple[dict[str, str], str, Any],
    ) -> None:
        headers, shipment_id, vehicle = shipment_setup
        trip = plan_shipment(client, headers, shipment_id, vehicle.id)

        response = client.patch(
            f"{TRIPS}/{trip['id']}/status",
            headers=headers,
            json={"status": "completed"},
        )
        assert response.status_code == 200, response.text

        shipment = client.get(f"{SHIPMENTS}/{shipment_id}", headers=headers).json()
        assert shipment["planning_status"] == PlanningStatus.COMPLETED

        position = client.get(
            f"{VEHICLES}/{vehicle.id}/position", headers=headers
        ).json()
        assert position["source"] == "trip"
        last_stop = max(trip["stops"], key=lambda stop: stop["sequence"])
        assert position["longitude"] == pytest.approx(last_stop["coordinate"][0])
        assert position["latitude"] == pytest.approx(last_stop["coordinate"][1])

    def test_repeating_completion_does_not_write_another_reading(
        self,
        client: TestClient,
        db: Session,
        shipment_setup: tuple[dict[str, str], str, Any],
    ) -> None:
        headers, shipment_id, vehicle = shipment_setup
        trip = plan_shipment(client, headers, shipment_id, vehicle.id)
        url = f"{TRIPS}/{trip['id']}/status"
        client.patch(url, headers=headers, json={"status": "completed"})
        client.patch(url, headers=headers, json={"status": "completed"})

        count = db.execute(
            select(func.count())
            .select_from(VehiclePosition)
            .where(VehiclePosition.trip_plan_id == trip["id"])
        ).scalar_one()
        assert count == 1

    def test_trip_reading_is_the_vehicle_position_without_gps(
        self,
        client: TestClient,
        shipment_setup: tuple[dict[str, str], str, Any],
    ) -> None:
        headers, shipment_id, vehicle = shipment_setup
        trip = plan_shipment(client, headers, shipment_id, vehicle.id)
        client.patch(
            f"{TRIPS}/{trip['id']}/status",
            headers=headers,
            json={"status": "completed"},
        )

        response = client.get(
            f"{SHIPMENTS}/{shipment_id}/vehicle-suggestions", headers=headers
        )

        row = next(
            row
            for row in response.json()["data"]
            if row["vehicle_id"] == str(vehicle.id)
        )
        assert row["position_source"] == "trip"
        assert row["is_position_stale"] is False
