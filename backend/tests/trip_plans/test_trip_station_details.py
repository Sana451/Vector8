"""Saved trip stops are enriched with the current fuel station record."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import UserRole
from tests.trip_plans.factories import (
    create_station,
    create_trip_plan,
    create_user_with_role,
    headers_for,
)

PREFIX = f"{settings.API_V1_STR}/trip-plans"


def _refuel_stop(body: dict) -> dict:
    return next(stop for stop in body["stops"] if stop["kind"] == "refuel")


def _with_station_id(stops: list[dict], station_id: uuid.UUID) -> list[dict]:
    """Return fresh stop dicts so the shared factory fixture is not mutated."""
    return [
        {**stop, "station_id": str(station_id)}
        if stop.get("kind") == "refuel"
        else stop
        for stop in stops
    ]


class TestStationDetails:
    def test_refuel_stop_carries_station_details(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        station = create_station(db, name="Love's #200")
        trip = create_trip_plan(db, owner=dispatcher)
        trip.stops_snapshot = _with_station_id(trip.stops_snapshot, station.id)
        db.add(trip)
        db.commit()

        response = client.get(
            f"{PREFIX}/{trip.id}", headers=headers_for(client, dispatcher, password)
        )

        assert response.status_code == 200
        station_details = _refuel_stop(response.json())["station"]
        assert station_details["name"] == "Love's #200"
        assert station_details["diesel_price"] == 5.76

    def test_stop_without_existing_station_has_no_details(
        self, client: TestClient, db: Session
    ) -> None:
        dispatcher, password = create_user_with_role(db, UserRole.DISPATCHER)
        trip = create_trip_plan(db, owner=dispatcher)
        trip.stops_snapshot = _with_station_id(trip.stops_snapshot, uuid.uuid4())
        db.add(trip)
        db.commit()

        response = client.get(
            f"{PREFIX}/{trip.id}", headers=headers_for(client, dispatcher, password)
        )

        assert response.status_code == 200
        assert _refuel_stop(response.json())["station"] is None
