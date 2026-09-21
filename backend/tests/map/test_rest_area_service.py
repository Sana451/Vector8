"""Tests for HerePoiService cache and fallback behaviour."""

import pytest
from sqlmodel import Session

from app.core.db import engine
from app.map.services import HerePoiService
from app.providers.exceptions import ProviderTimeoutError
from app.providers.geo import GeoJSONLineString, GeoJSONPoint
from app.providers.here.poi import HERE_BROWSE_MAX_LIMIT
from app.providers.schemas import LayerQuery, RestAreaCategory, RestAreaData


class FakeRestAreaProvider:
    def __init__(self, data=None, error=None):
        self.data = data or []
        self.error = error
        self.calls = 0

    async def search_along_route(self, query):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.data


class RecordingRestAreaProvider(FakeRestAreaProvider):
    def __init__(self, data=None, error=None):
        super().__init__(data=data, error=error)
        self.received_limits: list[int] = []

    async def search_along_route(self, query):
        self.received_limits.append(query.limit)
        return await super().search_along_route(query)


class FakeRestAreaRepository:
    def __init__(self, cached_rows=None):
        self.cached_rows = cached_rows or []
        self.replace_calls: list[dict] = []

    def get_valid(self, provider, request_hash):
        return self.cached_rows

    def replace_many(self, **kwargs):
        self.replace_calls.append(kwargs)
        return 1


@pytest.fixture
def layer_query() -> LayerQuery:
    return LayerQuery(
        path=GeoJSONLineString(
            coordinates=[(-87.9, 41.8), (-87.8, 41.85), (-87.7, 41.9)]
        ),
        radius_meters=5000,
        limit=25,
    )


@pytest.fixture
def rest_area() -> RestAreaData:
    return RestAreaData(
        provider="here",
        provider_place_id="here:pds:place:test-1",
        title="O'Hare Oasis Travel Plaza",
        position=GeoJSONPoint(coordinates=(-87.87654, 41.95012)),
        categories=[
            RestAreaCategory(id="700-7900-0131", name="Truck Parking", primary=True)
        ],
    )


@pytest.mark.asyncio
async def test_cache_hit_skips_provider(
    monkeypatch: pytest.MonkeyPatch, layer_query, rest_area
):
    with Session(engine) as session:
        provider = FakeRestAreaProvider(data=[rest_area])
        service = HerePoiService(provider=provider, session=session)  # type: ignore[arg-type]
        service.repository = FakeRestAreaRepository()  # type: ignore[assignment]
        monkeypatch.setattr(service, "_from_cache", lambda request_hash: [rest_area])

        result = await service.find_rest_areas(layer_query)

    assert provider.calls == 0
    assert result[0].provider_place_id == rest_area.provider_place_id


@pytest.mark.asyncio
async def test_cache_miss_calls_provider_and_persists(
    monkeypatch: pytest.MonkeyPatch,
    layer_query,
    rest_area,
):
    with Session(engine) as session:
        provider = FakeRestAreaProvider(data=[rest_area])
        service = HerePoiService(provider=provider, session=session)  # type: ignore[arg-type]
        repository = FakeRestAreaRepository()

        monkeypatch.setattr(service, "_from_cache", lambda request_hash: [])
        service.repository = repository  # type: ignore[assignment]

        result = await service.find_rest_areas(layer_query)

    assert provider.calls == 1
    assert len(result) == 1
    assert len(repository.replace_calls) == 1
    assert (
        repository.replace_calls[0]["rows"][0]["provider_place_id"]
        == rest_area.provider_place_id
    )


@pytest.mark.asyncio
async def test_force_refresh_bypasses_cache(
    monkeypatch: pytest.MonkeyPatch, layer_query, rest_area
):
    with Session(engine) as session:
        provider = FakeRestAreaProvider(data=[rest_area])
        service = HerePoiService(provider=provider, session=session)  # type: ignore[arg-type]
        repository = FakeRestAreaRepository()
        cache_reads = 0

        def fake_from_cache(_request_hash: str):
            nonlocal cache_reads
            cache_reads += 1
            return [rest_area]

        monkeypatch.setattr(service, "_from_cache", fake_from_cache)
        service.repository = repository  # type: ignore[assignment]

        await service.find_rest_areas(layer_query, force_refresh=True)

    assert provider.calls == 1
    assert cache_reads == 0


@pytest.mark.asyncio
async def test_provider_failure_falls_back_to_cache(
    monkeypatch: pytest.MonkeyPatch,
    layer_query,
    rest_area,
):
    with Session(engine) as session:
        provider = FakeRestAreaProvider(
            error=ProviderTimeoutError("timeout", provider="here")
        )
        service = HerePoiService(provider=provider, session=session)  # type: ignore[arg-type]
        service.repository = FakeRestAreaRepository()  # type: ignore[assignment]
        monkeypatch.setattr(service, "_from_cache", lambda request_hash: [rest_area])

        result = await service.find_rest_areas(layer_query, force_refresh=True)

    assert provider.calls == 1
    assert result[0].provider_place_id == rest_area.provider_place_id


@pytest.mark.asyncio
async def test_provider_failure_without_cache_propagates(
    monkeypatch: pytest.MonkeyPatch,
    layer_query,
):
    with Session(engine) as session:
        provider = FakeRestAreaProvider(
            error=ProviderTimeoutError("timeout", provider="here")
        )
        service = HerePoiService(provider=provider, session=session)  # type: ignore[arg-type]
        service.repository = FakeRestAreaRepository()  # type: ignore[assignment]
        monkeypatch.setattr(service, "_from_cache", lambda request_hash: [])

        with pytest.raises(ProviderTimeoutError):
            await service.find_rest_areas(layer_query)


@pytest.mark.asyncio
async def test_service_caps_limit_to_here_maximum(
    monkeypatch: pytest.MonkeyPatch, rest_area
):
    with Session(engine) as session:
        provider = RecordingRestAreaProvider(data=[rest_area])
        service = HerePoiService(provider=provider, session=session)  # type: ignore[arg-type]
        repository = FakeRestAreaRepository()

        monkeypatch.setattr(service, "_from_cache", lambda request_hash: [])
        service.repository = repository  # type: ignore[assignment]

        await service.find_rest_areas(
            LayerQuery(
                path=GeoJSONLineString(
                    coordinates=[(-87.9, 41.8), (-87.8, 41.85), (-87.7, 41.9)]
                ),
                radius_meters=5000,
                limit=250,
            )
        )

    assert provider.received_limits == [HERE_BROWSE_MAX_LIMIT]
