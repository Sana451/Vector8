"""Tests for the HERE rest area provider."""

import json
from pathlib import Path

import pytest

from app.providers.geo import GeoJSONLineString
from app.providers.here.poi import (
    HERE_BROWSE_MAX_LIMIT,
    HERE_EXCURSION_DISTANCE_RANKING,
    HerePoiProvider,
)
from app.providers.http import ProviderHTTPClient
from app.providers.schemas import RestAreaQuery

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "here"


def load_fixture(name: str) -> dict:
    with (FIXTURES_DIR / name).open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def build_query(*, ranking: str | None = None) -> RestAreaQuery:
    return RestAreaQuery(
        path=GeoJSONLineString(
            coordinates=[
                (-87.90, 41.80),
                (-87.80, 41.85),
                (-87.70, 41.90),
                (-87.60, 41.95),
            ]
        ),
        categories=["700-7900-0131", "400-4300-0199"],
        corridor_width_meters=1000,
        limit=25,
        ranking=ranking,
    )


@pytest.mark.asyncio
async def test_search_along_route_maps_confirmed_here_fields(
    monkeypatch: pytest.MonkeyPatch,
):
    payloads = {
        "700-7900-0131": load_fixture("truck_parking_discover.json"),
        "400-4300-0199": load_fixture("complete_rest_area_discover.json"),
    }

    async def fake_request_json(_self, method, path, *, params=None, **_kwargs):
        assert method == "GET"
        assert path == "/v1/browse"
        assert params is not None
        assert params["at"] == "41.8,-87.9"
        return payloads[params["categories"]]

    monkeypatch.setattr(ProviderHTTPClient, "request_json", fake_request_json)

    provider = HerePoiProvider()
    provider.api_key = "test-key"
    rest_areas = await provider.search_along_route(build_query())

    assert len(rest_areas) == 2
    first = next(item for item in rest_areas if item.provider_place_id.endswith("123"))
    assert first.provider == "here"
    assert first.position.coordinates == (-87.74529, 41.88978)
    assert len(first.access_points) == 2
    assert first.categories[0].id == "700-7900-0131"
    assert first.references[0].supplier is not None
    assert first.contacts[0]["phone"][0]["value"] == "+13125550123"
    assert first.opening_hours[0]["isOpen"] is True
    assert first.metadata == {
        "ontologyId": "here:cm:ontology:truck_parking",
        "distance": 9649,
        "providerPlaceId": "here:pds:place:840dr5ru-123",
    }


@pytest.mark.asyncio
async def test_search_along_route_merges_duplicate_provider_place_ids(
    monkeypatch: pytest.MonkeyPatch,
):
    payloads = {
        "700-7900-0131": load_fixture("complete_rest_area_discover.json"),
        "400-4300-0199": load_fixture("mixed_categories_discover.json"),
    }

    async def fake_request_json(_self, _method, _path, *, params=None, **_kwargs):
        assert params is not None
        return payloads[params["categories"]]

    monkeypatch.setattr(ProviderHTTPClient, "request_json", fake_request_json)

    provider = HerePoiProvider()
    provider.api_key = "test-key"
    rest_areas = await provider.search_along_route(build_query())

    oasis = next(item for item in rest_areas if item.provider_place_id.endswith("456"))
    category_ids = {category.id for category in oasis.categories}
    assert category_ids == {"700-7900-0131", "400-4300-0199"}
    assert (
        len([item for item in rest_areas if item.provider_place_id.endswith("456")])
        == 1
    )


@pytest.mark.asyncio
async def test_search_along_route_tolerates_missing_optional_fields(
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_request_json(_self, _method, _path, *, _params=None, **_kwargs):
        return load_fixture("missing_optional_fields_discover.json")

    monkeypatch.setattr(ProviderHTTPClient, "request_json", fake_request_json)

    provider = HerePoiProvider()
    provider.api_key = "test-key"
    rest_areas = await provider.search_along_route(
        RestAreaQuery(
            path=build_query().path,
            categories=["700-7900-0131"],
            corridor_width_meters=100,
            limit=10,
        )
    )

    assert len(rest_areas) == 1
    item = rest_areas[0]
    assert item.address is None
    assert item.access_points == []
    assert item.opening_hours == []
    assert item.contacts == []
    assert item.chains == []
    assert item.references == []
    assert item.ontology_id is None


@pytest.mark.asyncio
async def test_search_along_route_omits_ranking_by_default(
    monkeypatch: pytest.MonkeyPatch,
):
    recorded_rankings: list[str | None] = []

    async def fake_request_json(_self, _method, _path, *, params=None, **_kwargs):
        assert params is not None
        recorded_rankings.append(params.get("ranking"))
        return {"items": []}

    monkeypatch.setattr(ProviderHTTPClient, "request_json", fake_request_json)

    provider = HerePoiProvider()
    provider.api_key = "test-key"
    await provider.search_along_route(build_query())
    await provider.search_along_route(
        build_query(ranking=HERE_EXCURSION_DISTANCE_RANKING)
    )

    assert recorded_rankings[:2] == [None, None]
    assert recorded_rankings[2:] == [
        HERE_EXCURSION_DISTANCE_RANKING,
        HERE_EXCURSION_DISTANCE_RANKING,
    ]


@pytest.mark.asyncio
async def test_search_along_route_caps_limit_to_here_browse_max(
    monkeypatch: pytest.MonkeyPatch,
):
    recorded_limits: list[int] = []

    async def fake_request_json(_self, _method, _path, *, params=None, **_kwargs):
        assert params is not None
        recorded_limits.append(params["limit"])
        return {"items": []}

    monkeypatch.setattr(ProviderHTTPClient, "request_json", fake_request_json)

    provider = HerePoiProvider()
    provider.api_key = "test-key"
    await provider.search_along_route(
        RestAreaQuery(
            path=build_query().path,
            categories=["700-7900-0131", "400-4300-0199"],
            corridor_width_meters=100,
            limit=250,
        )
    )

    assert recorded_limits == [HERE_BROWSE_MAX_LIMIT, HERE_BROWSE_MAX_LIMIT]


def test_normalize_base_url_upgrades_legacy_discover_host():
    assert (
        HerePoiProvider._normalize_base_url("https://discover.search.hereapi.com/")
        == "https://browse.search.hereapi.com"
    )
    assert (
        HerePoiProvider._normalize_base_url("https://browse.search.hereapi.com")
        == "https://browse.search.hereapi.com"
    )
