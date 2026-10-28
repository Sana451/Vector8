"""Shared factories for trip plan tests.

Trip plans sit on top of three existing records (vehicle, route calculation,
optimization run), so the factories here build the whole chain and let a test
state only what it actually cares about.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.fleet.models import Vehicle, VehicleType
from app.fuel_optimization.domain import (
    FuelOptimizationAlgorithm,
    FuelOptimizationStatus,
)
from app.fuel_optimization.models import FuelOptimizationRun, FuelOptimizationStop
from app.map.models import FuelStation
from app.models import User, UserCreate, UserRole
from app.providers.geo import GeoJSONPoint
from app.routing.models import RouteCalculation
from app.routing.schemas import CalculateRouteRequest, RoutePlanningLocations
from app.trip_plans.domain import TripPlanStatus
from app.trip_plans.models import TripPlan
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string

STOPS_SNAPSHOT: list[dict[str, Any]] = [
    {
        "sequence": 0,
        "kind": "start",
        "label": "Origin",
        "coordinate": [-97.0, 40.0],
    },
    {
        "sequence": 1,
        "kind": "refuel",
        "label": "Love's #200",
        "station_id": str(uuid.uuid4()),
        "coordinate": [-93.5, 40.0],
        "route_offset_meters": "560000.00",
        "fuel_added_gallons": "21.0500",
        "fuel_price_per_gallon": "5.7600",
        "fuel_cost": "121.28",
        "detour_distance_meters": "3218.70",
        "detour_time_seconds": 120,
    },
    {
        "sequence": 2,
        "kind": "destination",
        "label": "Destination",
        "coordinate": [-90.0, 40.0],
    },
]


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


ROUTE_RESPONSE = {
    "routes": [
        {
            "summary": {
                "lengthInMeters": 1126540,
                "travelDurationInSeconds": 36000,
            },
            "legs": [
                {
                    "summary": {
                        "lengthInMeters": 563270,
                        "travelDurationInSeconds": 18000,
                    },
                    "path": {
                        "type": "LineString",
                        "coordinates": [[-97.0, 40.0], [-93.5, 40.0]],
                    },
                },
                {
                    "summary": {
                        "lengthInMeters": 563270,
                        "travelDurationInSeconds": 18000,
                    },
                    "path": {
                        "type": "LineString",
                        "coordinates": [[-93.5, 40.0], [-90.0, 40.0]],
                    },
                },
            ],
        }
    ]
}


BASE_REQUEST_DATA = CalculateRouteRequest(
    route_planning_locations=RoutePlanningLocations(
        origin=GeoJSONPoint(coordinates=(-97.0, 40.0)),
        destination=GeoJSONPoint(coordinates=(-90.0, 40.0)),
    )
).model_dump(mode="json")


def create_station(
    db: Session, *, name: str = "Love's #200", longitude: float = -93.5
) -> FuelStation:
    station = FuelStation(
        provider="internal",
        external_id=f"st-{uuid.uuid4()}",
        name=name,
        location=f"SRID=4326;POINT({longitude} 40.0)",
        diesel_price=5.76,
        payload={},
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db.add(station)
    db.commit()
    db.refresh(station)
    return station


def create_optimization_stop(
    db: Session, *, run_id: uuid.UUID, station_id: uuid.UUID, sequence: int = 1
) -> FuelOptimizationStop:
    stop = FuelOptimizationStop(
        optimization_run_id=run_id,
        sequence=sequence,
        station_id=station_id,
        route_offset_meters=Decimal("560000"),
        fuel_before_gallons=Decimal("10"),
        fuel_added_gallons=Decimal("21.05"),
        fuel_after_gallons=Decimal("31.05"),
        fuel_price_per_gallon=Decimal("5.76"),
        fuel_cost=Decimal("121.28"),
        detour_distance_meters=Decimal("3218.7"),
        detour_time_seconds=120,
    )
    db.add(stop)
    db.commit()
    return stop


def create_route(db: Session, *, suffix: str | None = None) -> RouteCalculation:
    route = RouteCalculation(
        provider="here",
        request_hash=f"trip-plan-{suffix or 'route'}-{uuid.uuid4()}",
        origin="SRID=4326;POINT(-97.0 40.0)",
        destination="SRID=4326;POINT(-90.0 40.0)",
        geometry="SRID=4326;LINESTRING(-97.0 40.0, -93.5 40.0, -90.0 40.0)",
        distance_meters=1126540,
        duration_seconds=36000,
        request_data=BASE_REQUEST_DATA,
        provider_response=ROUTE_RESPONSE,
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db.add(route)
    db.commit()
    db.refresh(route)
    return route


def create_vehicle(db: Session) -> Vehicle:
    vehicle = Vehicle(
        name="Truck 001",
        unit_number=f"TRK-{uuid.uuid4().hex[:8]}",
        vehicle_type=VehicleType.TRACTOR,
        tank_capacity_gallons=Decimal("150"),
        consumption_mpg=Decimal("8"),
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def create_optimization_run(
    db: Session, *, route_id: uuid.UUID, vehicle_id: uuid.UUID
) -> FuelOptimizationRun:
    run = FuelOptimizationRun(
        route_id=route_id,
        vehicle_id=vehicle_id,
        algorithm=FuelOptimizationAlgorithm.GREEDY,
        algorithm_version="1",
        status=FuelOptimizationStatus.SUCCESS,
        initial_fuel_gallons=Decimal("50"),
        total_fuel_consumed_gallons=Decimal("258"),
        total_fuel_purchased_gallons=Decimal("229"),
        total_fuel_cost=Decimal("1323.22"),
        total_detour_distance_meters=Decimal("14600"),
        total_detour_time_seconds=1087,
        number_of_stops=1,
        remaining_fuel_gallons=Decimal("13"),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def create_trip_plan(
    db: Session,
    *,
    owner: User,
    assigned_driver: User | None = None,
    status: TripPlanStatus = TripPlanStatus.REFINED,
    refined: bool = True,
    share_token: str | None = None,
) -> TripPlan:
    """Persist a trip plan together with everything it points at."""
    base_route = create_route(db, suffix="base")
    vehicle = create_vehicle(db)
    run = create_optimization_run(db, route_id=base_route.id, vehicle_id=vehicle.id)
    refined_route = create_route(db, suffix="refined") if refined else None

    trip_plan = TripPlan(
        name="Dallas run",
        owner_id=owner.id,
        assigned_driver_id=assigned_driver.id if assigned_driver else None,
        assigned_at=datetime.now(UTC) if assigned_driver else None,
        vehicle_id=vehicle.id,
        base_route_id=base_route.id,
        optimization_run_id=run.id,
        refined_route_id=refined_route.id if refined_route else None,
        refined_provider="here" if refined_route else None,
        status=status,
        stops_snapshot=STOPS_SNAPSHOT,
        base_distance_meters=1126540,
        base_duration_seconds=36000,
        refined_distance_meters=1130000 if refined_route else None,
        refined_duration_seconds=36600 if refined_route else None,
        share_token=share_token,
    )
    db.add(trip_plan)
    db.commit()
    db.refresh(trip_plan)
    return trip_plan
