from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

from app.fleet.models import (
    Vehicle,
    VehicleFuelProfile,
    VehicleFuelType,
    VehicleStatus,
    VehicleType,
)
from app.fuel_optimization.domain import FuelOptimizationStatus
from app.fuel_optimization.schemas import (
    FuelOptimizationCalculateRequest,
    FuelOptimizationConstraintsInput,
)
from app.fuel_optimization.service import OptimizeFuelUseCase
from app.providers.geo import GeoJSONPoint
from app.providers.schemas import FuelStationData

ROUTE_RESPONSE = {
    "routes": [
        {
            "summary": {"lengthInMeters": 1126540, "travelDurationInSeconds": 36000},
            "legs": [
                {
                    "summary": {
                        "lengthInMeters": 1126540,
                        "travelDurationInSeconds": 36000,
                    },
                    "path": {
                        "type": "LineString",
                        "coordinates": [[-97.0, 40.0], [-90.0, 40.0]],
                    },
                }
            ],
        }
    ]
}


class FakeVehicleRepository:
    def __init__(self, vehicle: Vehicle | None, profile: VehicleFuelProfile | None):
        self.vehicle = vehicle
        self.profile = profile

    def get(self, vehicle_id):
        return self.vehicle if self.vehicle and self.vehicle.id == vehicle_id else None

    def get_fuel_profile(self, fuel_profile_id):
        return (
            self.profile
            if self.profile and self.profile.id == fuel_profile_id
            else None
        )


class FakeRouteRepository:
    def __init__(self, route_row):
        self.route_row = route_row

    def get(self, route_id):
        return (
            self.route_row if self.route_row and self.route_row.id == route_id else None
        )


class FakeFuelStationRepository:
    def __init__(self, rows=None, *, side_effect=None):
        self.rows = rows
        self.side_effect = side_effect
        self.calls: list[dict] = []

    def find_along_route(self, **kwargs):
        self.calls.append(kwargs)
        if self.side_effect is not None:
            return self.side_effect(**kwargs)
        return self.rows


class FakeRunRepository:
    def __init__(self):
        self.created = None

    def create(self, **kwargs):
        self.created = kwargs
        return SimpleNamespace(id=uuid.uuid4())


def build_vehicle() -> tuple[Vehicle, VehicleFuelProfile]:
    profile = VehicleFuelProfile(
        id=uuid.uuid4(),
        name="Sleeper profile",
        fuel_type=VehicleFuelType.TRUCK_DIESEL,
        tank_capacity_gallons=Decimal("150"),
        usable_tank_capacity_gallons=Decimal("145"),
        consumption_mpg=Decimal("10"),
        reserve_gallons=Decimal("20"),
    )
    vehicle = Vehicle(
        id=uuid.uuid4(),
        name="Truck 001",
        unit_number="TRK-001",
        status=VehicleStatus.ACTIVE,
        vehicle_type=VehicleType.TRACTOR,
        fuel_profile_id=profile.id,
    )
    return vehicle, profile


def build_station_row(*, station_id: uuid.UUID):
    payload = FuelStationData(
        external_id="internal-1",
        name="Pilot",
        brand="Pilot",
        address="Test address",
        location=GeoJSONPoint(coordinates=(-95.0, 40.0)),
        diesel_price=Decimal("5.5000"),
        currency="USD",
        fuel_type="Truck Diesel",
        medium_truck_accessible=True,
        large_truck_accessible=True,
        raw={"seed": 1},
    ).model_dump(mode="json")
    return SimpleNamespace(
        id=station_id,
        payload=payload,
        diesel_price=Decimal("5.5000"),
        medium_truck_accessible=True,
        large_truck_accessible=True,
        distance_to_route_meters=100.0,
        progress_along_route=0.5,
    )


def build_route_row(*, route_id: uuid.UUID):
    return SimpleNamespace(
        id=route_id,
        distance_meters=1126540,
        duration_seconds=36000,
        provider_response=ROUTE_RESPONSE,
    )


def test_optimize_fuel_use_case_persists_run() -> None:
    vehicle, profile = build_vehicle()
    route_id = uuid.uuid4()
    route_row = build_route_row(route_id=route_id)
    station_id = uuid.uuid4()
    run_repository = FakeRunRepository()
    use_case = OptimizeFuelUseCase(
        vehicle_repository=FakeVehicleRepository(vehicle, profile),
        route_repository=FakeRouteRepository(route_row),
        fuel_station_repository=FakeFuelStationRepository(
            [build_station_row(station_id=station_id)]
        ),
        run_repository=run_repository,
    )

    response = use_case.execute(
        FuelOptimizationCalculateRequest(
            route_id=route_id,
            vehicle_id=vehicle.id,
            initial_fuel_gallons=Decimal("60"),
        )
    )

    assert response.route_id == route_id
    assert response.vehicle_id == vehicle.id
    assert response.status in {
        FuelOptimizationStatus.SUCCESS,
        FuelOptimizationStatus.INFEASIBLE,
    }
    assert response.explanation.summary
    assert response.explanation.outcome
    assert response.explanation.key_points
    assert response.explanation.warnings
    assert isinstance(response.explanation.skipped_station_stats, list)
    assert response.debug is None
    assert run_repository.created is not None
    assert run_repository.created["route_id"] == route_id
    assert run_repository.created["vehicle_id"] == vehicle.id


def test_optimize_fuel_use_case_includes_debug_when_requested() -> None:
    vehicle, profile = build_vehicle()
    route_id = uuid.uuid4()
    route_row = build_route_row(route_id=route_id)
    station_id = uuid.uuid4()
    run_repository = FakeRunRepository()
    use_case = OptimizeFuelUseCase(
        vehicle_repository=FakeVehicleRepository(vehicle, profile),
        route_repository=FakeRouteRepository(route_row),
        fuel_station_repository=FakeFuelStationRepository(
            [build_station_row(station_id=station_id)]
        ),
        run_repository=run_repository,
    )

    response = use_case.execute(
        FuelOptimizationCalculateRequest(
            route_id=route_id,
            vehicle_id=vehicle.id,
            initial_fuel_gallons=Decimal("60"),
            include_debug=True,
        )
    )

    assert response.debug is not None
    assert "candidate_builder" in response.debug
    assert "algorithm_trace" in response.debug
    assert isinstance(response.debug["algorithm_trace"], list)
    assert response.debug["algorithm_trace"][0]["step"] == "start"
    assert response.debug["algorithm_trace"][-1]["step"] in {"finish", "stop"}
    assert any(step["step"] == "arrival" for step in response.debug["algorithm_trace"])
    assert "max_allowed_detour_seconds" not in response.debug["effective_constraints"]
    assert (
        "apply_detour_time_limit_if_present"
        not in response.debug["candidate_builder"]["metadata"]["filter_sequence"]
    )
    assert "detour_time_seconds" in response.debug["candidate_builder"]["candidates"][0]


def test_request_schema_removes_detour_time_constraint_and_examples() -> None:
    constraints_schema = FuelOptimizationConstraintsInput.model_json_schema()
    request_schema = FuelOptimizationCalculateRequest.model_json_schema()

    assert "max_allowed_detour_seconds" not in constraints_schema["properties"]
    assert request_schema["examples"][0]["constraints"] == {
        "max_allowed_detour_meters": "100000"
    }


def test_candidate_search_uses_default_radius_when_requested_detour_is_smaller() -> (
    None
):
    vehicle, profile = build_vehicle()
    route_id = uuid.uuid4()
    route_row = build_route_row(route_id=route_id)
    station_repository = FakeFuelStationRepository(
        [build_station_row(station_id=uuid.uuid4())]
    )
    use_case = OptimizeFuelUseCase(
        vehicle_repository=FakeVehicleRepository(vehicle, profile),
        route_repository=FakeRouteRepository(route_row),
        fuel_station_repository=station_repository,
        run_repository=FakeRunRepository(),
    )

    response = use_case.execute(
        FuelOptimizationCalculateRequest(
            route_id=route_id,
            vehicle_id=vehicle.id,
            initial_fuel_gallons=Decimal("60"),
            include_debug=True,
            constraints={"max_allowed_detour_meters": Decimal("1000")},
        )
    )

    assert station_repository.calls[0]["radius_meters"] == 5000
    metadata = response.debug["candidate_builder"]["metadata"]
    assert metadata["default_search_radius_meters"] == 5000
    assert metadata["effective_search_radius_meters"] == 5000
    assert metadata["requested_max_detour_meters"] == 1000


def test_candidate_search_expands_radius_when_requested_detour_is_larger() -> None:
    vehicle, profile = build_vehicle()
    route_id = uuid.uuid4()
    route_row = build_route_row(route_id=route_id)
    station_repository = FakeFuelStationRepository(
        [build_station_row(station_id=uuid.uuid4())]
    )
    use_case = OptimizeFuelUseCase(
        vehicle_repository=FakeVehicleRepository(vehicle, profile),
        route_repository=FakeRouteRepository(route_row),
        fuel_station_repository=station_repository,
        run_repository=FakeRunRepository(),
    )

    response = use_case.execute(
        FuelOptimizationCalculateRequest(
            route_id=route_id,
            vehicle_id=vehicle.id,
            initial_fuel_gallons=Decimal("60"),
            include_debug=True,
            constraints={"max_allowed_detour_meters": Decimal("20000")},
        )
    )

    assert station_repository.calls[0]["radius_meters"] == 20000
    metadata = response.debug["candidate_builder"]["metadata"]
    assert metadata["default_search_radius_meters"] == 5000
    assert metadata["effective_search_radius_meters"] == 20000
    assert metadata["requested_max_detour_meters"] == 20000


def test_expanded_search_radius_makes_farther_station_visible_before_detour_filtering() -> (
    None
):
    vehicle, profile = build_vehicle()
    route_id = uuid.uuid4()
    route_row = build_route_row(route_id=route_id)
    station_id = uuid.uuid4()

    def find_along_route(**kwargs):
        if kwargs["radius_meters"] < 12000:
            return []
        station = build_station_row(station_id=station_id)
        station.distance_to_route_meters = 12000.0
        return [station]

    station_repository = FakeFuelStationRepository(side_effect=find_along_route)
    use_case = OptimizeFuelUseCase(
        vehicle_repository=FakeVehicleRepository(vehicle, profile),
        route_repository=FakeRouteRepository(route_row),
        fuel_station_repository=station_repository,
        run_repository=FakeRunRepository(),
    )

    response = use_case.execute(
        FuelOptimizationCalculateRequest(
            route_id=route_id,
            vehicle_id=vehicle.id,
            initial_fuel_gallons=Decimal("60"),
            include_debug=True,
            constraints={"max_allowed_detour_meters": Decimal("20000")},
        )
    )

    assert station_repository.calls[0]["radius_meters"] == 20000
    assert response.debug["candidate_builder"]["candidates"] == []
    audit = response.debug["candidate_builder"]["audit"]
    assert len(audit) == 1
    assert audit[0]["station_id"] == str(station_id)
    assert audit[0]["reason"] == "detour_distance_limit_exceeded"
    assert audit[0]["included"] is False
    assert audit[0]["distance_from_route_meters"] == "12000.0"
    assert audit[0]["detour_distance_meters"] == "24000.0"
    assert audit[0]["max_allowed_detour_meters"] == "20000"


def test_candidate_builder_keeps_detour_time_as_informational_only() -> None:
    vehicle, profile = build_vehicle()
    route_id = uuid.uuid4()
    route_row = build_route_row(route_id=route_id)
    station_id = uuid.uuid4()
    station = build_station_row(station_id=station_id)
    station.distance_to_route_meters = 9000.0

    use_case = OptimizeFuelUseCase(
        vehicle_repository=FakeVehicleRepository(vehicle, profile),
        route_repository=FakeRouteRepository(route_row),
        fuel_station_repository=FakeFuelStationRepository([station]),
        run_repository=FakeRunRepository(),
    )

    response = use_case.execute(
        FuelOptimizationCalculateRequest(
            route_id=route_id,
            vehicle_id=vehicle.id,
            initial_fuel_gallons=Decimal("60"),
            include_debug=True,
            constraints={"max_allowed_detour_meters": Decimal("20000")},
        )
    )

    candidates = response.debug["candidate_builder"]["candidates"]
    assert len(candidates) == 1
    assert candidates[0]["station_id"] == str(station_id)
    assert candidates[0]["detour_time_seconds"] > 0
    assert (
        response.debug["candidate_builder"]["audit"][0]["reason"]
        == "candidate_included"
    )
