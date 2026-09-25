from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app.fleet.models import Vehicle, VehicleFuelProfile
from app.fuel_optimization.models import FuelOptimizationRun, FuelOptimizationStop
from app.map.models import FuelStation
from app.map.repository import FuelStationRepository
from app.map.services import FuelService
from app.providers.geo import GeoJSONPoint
from app.providers.schemas import FuelStationData
from app.routing.models import RouteCalculation

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


def _seed_internal_station(db: Session) -> uuid.UUID:
    station = FuelStationData(
        external_id="internal-optimization-1",
        name="Pilot",
        brand="Pilot",
        address="Optimized stop",
        location=GeoJSONPoint(coordinates=(-93.5, 40.0)),
        diesel_price=5.6321,
        currency="USD",
        fuel_type="Truck Diesel",
        medium_truck_accessible=True,
        large_truck_accessible=True,
        raw={"seed": 1},
    )
    repository = FuelStationRepository(db)
    repository.upsert_many(
        provider="internal",
        stations=[FuelService._to_row(station, last_imported_at=datetime.now(UTC))],
        ttl_seconds=86400,
        persist_internal=True,
    )
    row = db.exec(
        select(FuelStation).where(FuelStation.external_id == station.external_id)
    ).one()
    return row.id


class TestFuelOptimizationRouter:
    def test_calculate_optimization_success(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        db.exec(delete(FuelOptimizationStop))
        db.exec(delete(FuelOptimizationRun))
        db.exec(delete(Vehicle))
        db.exec(delete(VehicleFuelProfile))
        db.exec(delete(FuelStation))
        db.exec(delete(RouteCalculation))
        db.commit()

        route = RouteCalculation(
            provider="tomtom",
            request_hash="route-optimization-1",
            origin="SRID=4326;POINT(-97.0 40.0)",
            destination="SRID=4326;POINT(-90.0 40.0)",
            geometry="SRID=4326;LINESTRING(-97.0 40.0, -90.0 40.0)",
            distance_meters=1126540,
            duration_seconds=36000,
            request_data={"seed": 1},
            provider_response=ROUTE_RESPONSE,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        db.add(route)
        db.commit()
        db.refresh(route)

        vehicle_response = client.post(
            "/api/v1/vehicles/",
            headers=superuser_token_headers,
            json={
                "name": "Truck 001",
                "unit_number": "TRK-OPT-001",
                "vehicle_type": "tractor",
                "fuel_profile": {
                    "name": "Optimization profile",
                    "fuel_type": "truck_diesel",
                    "tank_capacity_gallons": "150",
                    "usable_tank_capacity_gallons": "145",
                    "consumption_mpg": "10",
                    "reserve_gallons": "20",
                },
            },
        )
        assert vehicle_response.status_code == 200
        vehicle_id = vehicle_response.json()["id"]

        response = client.post(
            "/api/v1/fuel-optimization/calculate",
            headers=superuser_token_headers,
            json={
                "route_id": str(route.id),
                "vehicle_id": vehicle_id,
                "algorithm": "greedy",
                "initial_fuel_gallons": "60",
                "constraints": {"max_allowed_detour_meters": "10000"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["route_id"] == str(route.id)
        assert data["vehicle_id"] == vehicle_id
        assert data["algorithm"] == "greedy"
        assert data["status"] in {"success", "infeasible"}
        assert "optimization_run_id" in data
        assert "explanation" in data
        assert data["explanation"]["summary"]
        assert data["explanation"]["outcome"]
        assert isinstance(data["explanation"]["key_points"], list)
        assert isinstance(data["explanation"]["warnings"], list)
        assert isinstance(data["explanation"]["skipped_station_stats"], list)
        assert data["debug"] is None

        run = db.exec(select(FuelOptimizationRun)).first()
        assert run is not None
        assert run.route_id == route.id
        assert run.vehicle_id == uuid.UUID(vehicle_id)
