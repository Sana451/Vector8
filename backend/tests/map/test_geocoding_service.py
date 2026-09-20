"""Tests for geocoding schemas and service."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from pydantic import ValidationError
from sqlmodel import Session, delete

from app.core.db import engine
from app.geocoding.repository import GeocodingCacheEntry
from app.geocoding.schemas import GeocodingResult, MapPointInput
from app.geocoding.service import GeocodingService
from app.providers.geo import GeoJSONPoint


class FakeGeocodingProvider:
    """Provider stub returning deterministic geocoding results."""

    def __init__(self, result: GeocodingResult):
        self.result = result
        self.calls: list[str] = []

    async def search(self, query: str) -> GeocodingResult:
        self.calls.append(query)
        return self.result


@pytest.fixture(autouse=True)
def clear_geocoding_cache() -> Generator[None]:
    """Keep geocoding cache isolated between tests."""
    with Session(engine) as session:
        session.exec(delete(GeocodingCacheEntry))
        session.commit()
    yield
    with Session(engine) as session:
        session.exec(delete(GeocodingCacheEntry))
        session.commit()


class TestMapPointInput:
    """Validation of address-or-location point inputs."""

    def test_accepts_address(self):
        point = MapPointInput(address="1521 Hickory Trail Allen TX 75002")
        assert point.address == "1521 Hickory Trail Allen TX 75002"
        assert point.location is None

    def test_accepts_coordinates(self):
        point = MapPointInput(location=GeoJSONPoint(coordinates=(-96.6705, 33.1032)))
        assert point.location is not None
        assert point.location.coordinates == (-96.6705, 33.1032)

    def test_rejects_both_fields(self):
        with pytest.raises(ValidationError) as exc_info:
            MapPointInput(
                address="1521 Hickory Trail Allen TX 75002",
                location=GeoJSONPoint(coordinates=(-96.6705, 33.1032)),
            )
        assert "Either address or location must be provided." in str(exc_info.value)

    def test_rejects_missing_both_fields(self):
        with pytest.raises(ValidationError) as exc_info:
            MapPointInput()
        assert "Either address or location must be provided." in str(exc_info.value)


class TestGeocodingService:
    """Caching and normalization semantics for geocoding."""

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        result = GeocodingResult(
            formatted_address="1521 Hickory Trail, Allen, TX 75002",
            location=GeoJSONPoint(coordinates=(-96.6705, 33.1032)),
            provider_id="tt-1",
        )
        provider = FakeGeocodingProvider(result)

        with Session(engine) as session:
            service = GeocodingService(provider=provider, session=session)
            first = await service.search("1521 Hickory Trail Allen TX 75002")
            second = await service.search("1521 Hickory Trail Allen TX 75002")

        assert first.formatted_address == second.formatted_address
        assert second.location.coordinates == (-96.6705, 33.1032)
        assert provider.calls == ["1521 Hickory Trail Allen TX 75002"]

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        result = GeocodingResult(
            formatted_address="3660 Gateway Street, Springfield, OR 97477",
            location=GeoJSONPoint(coordinates=(-123.0463, 44.0860)),
            provider_id="tt-2",
        )
        provider = FakeGeocodingProvider(result)

        with Session(engine) as session:
            service = GeocodingService(provider=provider, session=session)
            response = await service.search("3660 Gateway Street Springfield OR 97477")

        assert response.formatted_address == result.formatted_address
        assert provider.calls == ["3660 Gateway Street Springfield OR 97477"]

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_cache(self):
        result = GeocodingResult(
            formatted_address="1521 Hickory Trail, Allen, TX 75002",
            location=GeoJSONPoint(coordinates=(-96.6705, 33.1032)),
            provider_id="tt-1",
        )
        provider = FakeGeocodingProvider(result)

        with Session(engine) as session:
            service = GeocodingService(provider=provider, session=session)
            await service.search("1521 Hickory Trail Allen TX 75002")
            await service.search(
                "1521 Hickory Trail Allen TX 75002",
                force_refresh=True,
            )

        assert provider.calls == [
            "1521 Hickory Trail Allen TX 75002",
            "1521 Hickory Trail Allen TX 75002",
        ]

    @pytest.mark.asyncio
    async def test_normalize_point_returns_coordinates_directly(self):
        result = GeocodingResult(
            formatted_address="unused",
            location=GeoJSONPoint(coordinates=(-96.6705, 33.1032)),
        )
        provider = FakeGeocodingProvider(result)

        with Session(engine) as session:
            service = GeocodingService(provider=provider, session=session)
            point = await service.normalize_point(
                MapPointInput(location=GeoJSONPoint(coordinates=(-96.6705, 33.1032)))
            )

        assert point.coordinates == (-96.6705, 33.1032)
        assert provider.calls == []
