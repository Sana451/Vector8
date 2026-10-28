from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.fleet.models import Vehicle
from app.models import UserRole
from tests.trip_plans.factories import (
    create_user_with_role,
    create_vehicle,
    headers_for,
)


class TestVehicleRouter:
    def test_vehicle_routing_fields(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        db.exec(delete(Vehicle))
        db.commit()
        base = {
            "name": "Box 22",
            "unit_number": "BOX-22",
            "vehicle_type": "truck",
            "tank_capacity_gallons": "50",
            "consumption_mpg": "9",
        }
        ok = client.post(
            "/api/v1/vehicles/",
            headers=superuser_token_headers,
            json={
                **base,
                "height_in": 150,
                "width_in": 96,
                "length_in": 312,
                "gross_weight_lbs": 26000,
                "payload_capacity_lbs": 8300,
                "axle_count": 2,
            },
        )
        assert ok.status_code == 200
        body = ok.json()
        assert body["payload_capacity_lbs"] == 8300
        assert body["trailer_count"] == 0
        assert "routing_profile_id" not in body

        bad = client.post(
            "/api/v1/vehicles/",
            headers=superuser_token_headers,
            json={
                **base,
                "unit_number": "BOX-23",
                "gross_weight_lbs": 5000,
                "payload_capacity_lbs": 8300,
            },
        )
        assert bad.status_code in (400, 422)

        bad_trailer = client.post(
            "/api/v1/vehicles/",
            headers=superuser_token_headers,
            json={**base, "unit_number": "BOX-24", "trailer_length_in": 200},
        )
        assert bad_trailer.status_code in (400, 422)

    def test_vehicle_crud_lifecycle(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        db.exec(delete(Vehicle))
        db.commit()

        create_response = client.post(
            "/api/v1/vehicles/",
            headers=superuser_token_headers,
            json={
                "name": "Truck 001",
                "unit_number": "TRK-001",
                "vehicle_type": "tractor",
                "fuel_type": "truck_diesel",
                "tank_capacity_gallons": "150",
                "consumption_mpg": "6.8",
            },
        )
        assert create_response.status_code == 200
        vehicle = create_response.json()
        assert vehicle["unit_number"] == "TRK-001"
        assert "fuel_profile" not in vehicle
        assert vehicle["consumption_mpg"] == "6.800"
        # usable_tank_capacity_gallons should be automatically calculated as 95% of tank capacity
        assert vehicle["usable_tank_capacity_gallons"] == "142.500000"

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
                "consumption_mpg": "7.0",
            },
        )
        assert patch_response.status_code == 200
        patched = patch_response.json()
        assert patched["status"] == "maintenance"
        assert patched["consumption_mpg"] == "7.000"

        delete_response = client.delete(
            f"/api/v1/vehicles/{vehicle_id}",
            headers=superuser_token_headers,
        )
        assert delete_response.status_code == 200
        assert delete_response.json()["message"] == "Vehicle deleted successfully"


class TestVehicleAccessByRole:
    def test_dispatcher_can_read_but_not_change_the_fleet(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        headers = headers_for(client, dispatcher, password)
        vehicle = create_vehicle(db)

        listing = client.get("/api/v1/vehicles/", headers=headers)
        single = client.get(f"/api/v1/vehicles/{vehicle.id}", headers=headers)
        patched = client.patch(
            f"/api/v1/vehicles/{vehicle.id}", headers=headers, json={"name": "x"}
        )
        deleted = client.delete(f"/api/v1/vehicles/{vehicle.id}", headers=headers)

        assert listing.status_code == 200
        assert single.status_code == 200
        assert patched.status_code == 403
        assert deleted.status_code == 403

    def test_driver_cannot_read_the_fleet(
        self, client: TestClient, db: Session
    ) -> None:
        driver, password = create_user_with_role(db, UserRole.DRIVER)

        response = client.get(
            "/api/v1/vehicles/", headers=headers_for(client, driver, password)
        )

        assert response.status_code == 403
