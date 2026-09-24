from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, delete, select

from app.map.models import FuelStation
from app.map.repository import FuelStationRepository
from app.providers.geo import GeoJSONPoint, point_to_wkt
from app.providers.schemas import FuelStationData

ROUTE_COORDINATES = [(-96.0, 40.0), (-95.9, 40.0)]
RADIUS_METERS = 500


@pytest.fixture(autouse=True)
def clear_fuel_stations(db: Session):
    db.exec(delete(FuelStation))
    db.commit()
    yield
    db.exec(delete(FuelStation))
    db.commit()


@pytest.fixture
def repository(db: Session) -> FuelStationRepository:
    return FuelStationRepository(db)


def _station_row(
    *,
    external_id: str,
    longitude: float,
    latitude: float,
    diesel_price: float = 4.0,
    last_imported_at: datetime | None = None,
) -> dict:
    station = FuelStationData(
        external_id=external_id,
        name=external_id,
        brand="Test Brand",
        address="Test Address",
        location=GeoJSONPoint(coordinates=(longitude, latitude)),
        diesel_price=diesel_price,
        currency="USD",
        fuel_type="Truck Diesel",
        medium_truck_accessible=True,
        large_truck_accessible=True,
        raw={"seed": external_id},
    )
    return {
        "external_id": station.external_id,
        "name": station.name,
        "brand": station.brand,
        "address": station.address,
        "location": point_to_wkt(longitude, latitude),
        "diesel_price": station.diesel_price,
        "medium_truck_accessible": station.medium_truck_accessible,
        "large_truck_accessible": station.large_truck_accessible,
        "payload": station.model_dump(mode="json"),
        "last_imported_at": last_imported_at,
    }


def _set_expires_at(db: Session, *, external_id: str, expires_at: datetime) -> None:
    row = db.exec(
        select(FuelStation).where(FuelStation.external_id == external_id)
    ).one()
    row.expires_at = expires_at
    db.add(row)
    db.commit()


def test_internal_provider_ignores_ttl(
    repository: FuelStationRepository, db: Session
) -> None:
    repository.upsert_many(
        provider="internal",
        stations=[
            _station_row(
                external_id="internal-expired",
                longitude=-95.97,
                latitude=40.0004,
                last_imported_at=datetime.now(UTC),
            )
        ],
        ttl_seconds=60,
        persist_internal=True,
    )
    _set_expires_at(
        db,
        external_id="internal-expired",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )

    rows = repository.find_along_route(
        coordinates=ROUTE_COORDINATES,
        radius_meters=RADIUS_METERS,
        limit=10,
        provider="internal",
    )

    assert [row.external_id for row in rows] == ["internal-expired"]


def test_external_provider_still_uses_ttl(
    repository: FuelStationRepository,
    db: Session,
) -> None:
    repository.upsert_many(
        provider="here",
        stations=[
            _station_row(
                external_id="external-fresh", longitude=-95.97, latitude=40.0004
            ),
            _station_row(
                external_id="external-expired", longitude=-95.96, latitude=40.0004
            ),
        ],
        ttl_seconds=60,
    )
    _set_expires_at(
        db,
        external_id="external-expired",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )

    rows = repository.find_along_route(
        coordinates=ROUTE_COORDINATES,
        radius_meters=RADIUS_METERS,
        limit=10,
        provider="here",
    )

    assert [row.external_id for row in rows] == ["external-fresh"]


def test_find_along_route_filters_outside_corridor(
    repository: FuelStationRepository,
) -> None:
    repository.upsert_many(
        provider="internal",
        stations=[
            _station_row(
                external_id="inside",
                longitude=-95.97,
                latitude=40.0004,
                last_imported_at=datetime.now(UTC),
            ),
            _station_row(
                external_id="outside",
                longitude=-95.97,
                latitude=40.0200,
                last_imported_at=datetime.now(UTC),
            ),
        ],
        ttl_seconds=60,
        persist_internal=True,
    )

    rows = repository.find_along_route(
        coordinates=ROUTE_COORDINATES,
        radius_meters=RADIUS_METERS,
        limit=10,
        provider="internal",
    )

    assert [row.external_id for row in rows] == ["inside"]


def test_find_along_route_orders_by_progress_then_distance(
    repository: FuelStationRepository,
) -> None:
    repository.upsert_many(
        provider="internal",
        stations=[
            _station_row(
                external_id="later-close",
                longitude=-95.95,
                latitude=40.0004,
                last_imported_at=datetime.now(UTC),
            ),
            _station_row(
                external_id="early-far",
                longitude=-95.97,
                latitude=40.0016,
                last_imported_at=datetime.now(UTC),
            ),
            _station_row(
                external_id="early-close",
                longitude=-95.97,
                latitude=40.0004,
                last_imported_at=datetime.now(UTC),
            ),
        ],
        ttl_seconds=60,
        persist_internal=True,
    )

    rows = repository.find_along_route(
        coordinates=ROUTE_COORDINATES,
        radius_meters=RADIUS_METERS,
        limit=10,
        provider="internal",
    )

    assert [row.external_id for row in rows] == [
        "early-close",
        "early-far",
        "later-close",
    ]
    progress_0 = rows[0].progress_along_route
    progress_1 = rows[1].progress_along_route
    progress_2 = rows[2].progress_along_route
    distance_0 = rows[0].distance_to_route_meters
    distance_1 = rows[1].distance_to_route_meters

    assert progress_0 == pytest.approx(progress_1)
    assert distance_0 < distance_1
    assert progress_1 < progress_2
    assert distance_0 == pytest.approx(44.0, rel=0.4)
