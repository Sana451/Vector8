from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest

from app.map.models import FuelStation
from app.map.repository import FuelStationRepository
from app.providers.exceptions import ProviderUnavailableError
from app.providers.fuel.internal import InternalFuelStationProvider
from app.providers.geo import GeoJSONLineString, GeoJSONPoint, point_to_wkt
from app.providers.schemas import FuelStationData, LayerQuery


class FakeFuelStationRepository:
    def __init__(self, rows: list[FuelStation] | None = None):
        self.rows = rows or []
        self.calls: list[dict[str, object]] = []

    def find_along_route(self, **kwargs):
        self.calls.append(kwargs)
        return self.rows


def _fuel_station_row() -> FuelStation:
    payload = FuelStationData(
        external_id="internal-1",
        name="Pilot",
        brand="Pilot",
        address="123 Truck Stop Rd",
        location=GeoJSONPoint(coordinates=(-95.97, 40.0004)),
        diesel_price=3.99,
        currency="USD",
        fuel_type="Truck Diesel",
        medium_truck_accessible=True,
        large_truck_accessible=True,
        raw={"source": "seed"},
    ).model_dump(mode="json")
    row = FuelStation(
        provider="internal",
        external_id="internal-1",
        name="Pilot",
        brand="Pilot",
        address="123 Truck Stop Rd",
        location=point_to_wkt(-95.97, 40.0004),
        diesel_price=3.99,
        medium_truck_accessible=True,
        large_truck_accessible=True,
        payload=payload,
        last_imported_at=datetime.now(UTC),
        expires_at=datetime.now(UTC),
    )
    object.__setattr__(row, "distance_to_route_meters", 123.4)
    object.__setattr__(row, "progress_along_route", 0.42)
    return row


@pytest.fixture
def layer_query() -> LayerQuery:
    return LayerQuery(
        path=GeoJSONLineString(coordinates=[(-96.0, 40.0), (-95.9, 40.0)]),
        radius_meters=500,
        limit=10,
    )


@pytest.mark.asyncio
async def test_internal_provider_reads_from_repository(layer_query: LayerQuery):
    repository = FakeFuelStationRepository(rows=[_fuel_station_row()])
    provider = InternalFuelStationProvider(
        repository=cast(FuelStationRepository, repository)
    )

    stations = await provider.find_stations(layer_query)

    assert len(repository.calls) == 1
    assert repository.calls[0] == {
        "coordinates": layer_query.coordinates,
        "radius_meters": layer_query.radius_meters,
        "limit": layer_query.limit,
        "provider": "internal",
    }
    assert len(stations) == 1
    assert stations[0].external_id == "internal-1"
    assert stations[0].distance_meters == pytest.approx(123.4)
    assert stations[0].diesel_price == pytest.approx(3.99)


@pytest.mark.asyncio
async def test_internal_provider_requires_repository(layer_query: LayerQuery):
    provider = InternalFuelStationProvider()

    with pytest.raises(ProviderUnavailableError) as exc_info:
        await provider.find_stations(layer_query)

    assert exc_info.value.provider == "internal"
