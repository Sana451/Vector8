from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.fleet.models import Vehicle, VehicleFuelProfile


class TestVehicleRouter:
    def test_vehicle_crud_lifecycle(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        db.exec(delete(Vehicle))
        db.exec(delete(VehicleFuelProfile))
        db.commit()

        create_response = client.post(
            "/api/v1/vehicles/",
            headers=superuser_token_headers,
            json={
                "name": "Truck 001",
                "unit_number": "TRK-001",
                "vehicle_type": "tractor",
                "fuel_profile": {
                    "name": "Sleeper profile",
                    "fuel_type": "truck_diesel",
                    "tank_capacity_gallons": "150",
                    "usable_tank_capacity_gallons": "145",
                    "consumption_mpg": "6.8",
                    "reserve_gallons": "20",
                },
            },
        )
        assert create_response.status_code == 200
        vehicle = create_response.json()
        assert vehicle["unit_number"] == "TRK-001"
        assert vehicle["fuel_profile"]["consumption_mpg"] == "6.800"

        vehicle_id = vehicle["id"]
        list_response = client.get(
            "/api/v1/vehicles/",
            headers=superuser_token_headers,
        )
        assert list_response.status_code == 200
        assert list_response.json()["count"] >= 1

        get_response = client.get(
            f"/api/v1/vehicles/{vehicle_id}",
            headers=superuser_token_headers,
        )
        assert get_response.status_code == 200
        assert get_response.json()["id"] == vehicle_id

        patch_response = client.patch(
            f"/api/v1/vehicles/{vehicle_id}",
            headers=superuser_token_headers,
            json={
                "status": "maintenance",
                "fuel_profile": {"reserve_gallons": "25"},
            },
        )
        assert patch_response.status_code == 200
        patched = patch_response.json()
        assert patched["status"] == "maintenance"
        assert patched["fuel_profile"]["reserve_gallons"] == "25.0000"

        delete_response = client.delete(
            f"/api/v1/vehicles/{vehicle_id}",
            headers=superuser_token_headers,
        )
        assert delete_response.status_code == 200
        assert delete_response.json()["message"] == "Vehicle deleted successfully"
