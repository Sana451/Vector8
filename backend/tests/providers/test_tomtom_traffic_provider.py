"""Tests for the TomTom traffic provider."""

import math

import pytest

from app.providers.exceptions import ProviderBadRequestError
from app.providers.geo import GeoJSONLineString
from app.providers.http import ProviderHTTPClient
from app.providers.schemas import LayerQuery
from app.providers.tomtom.traffic import TomTomTrafficProvider


def _bbox_area_square_km(bbox: tuple[float, float, float, float]) -> float:
    min_lon, min_lat, max_lon, max_lat = bbox
    mean_lat_radians = math.radians((min_lat + max_lat) / 2)
    width_km = (max_lon - min_lon) * 111.32 * max(math.cos(mean_lat_radians), 1e-6)
    height_km = (max_lat - min_lat) * 111.32
    return width_km * height_km


@pytest.mark.asyncio
async def test_get_traffic_splits_large_route_into_tomtom_safe_bboxes(
    monkeypatch: pytest.MonkeyPatch,
):
    recorded_bboxes: list[tuple[float, float, float, float]] = []

    async def fake_request_json(_self, method, _path, *, params=None, **_kwargs):
        assert method == "GET"
        assert params is not None
        recorded_bboxes.append(
            tuple(float(value) for value in params["bbox"].split(","))
        )
        return {"incidents": []}

    monkeypatch.setattr(ProviderHTTPClient, "request_json", fake_request_json)

    provider = TomTomTrafficProvider()
    provider.api_key = "test-key"

    result = await provider.get_traffic(
        LayerQuery(
            path=GeoJSONLineString(
                coordinates=[(-96.6705, 33.1032), (-123.0463, 44.0860)]
            ),
            radius_meters=5000,
            limit=25,
        )
    )

    assert result.provider == "tomtom"
    assert len(recorded_bboxes) > 1
    assert all(_bbox_area_square_km(bbox) <= 10_000.0 for bbox in recorded_bboxes)


@pytest.mark.asyncio
async def test_get_traffic_deduplicates_incidents_across_split_bboxes(
    monkeypatch: pytest.MonkeyPatch,
):
    payloads = [
        {
            "incidents": [
                {
                    "geometry": {"type": "Point", "coordinates": [-96.67, 33.10]},
                    "properties": {
                        "id": "dup-1",
                        "iconCategory": "1",
                        "magnitudeOfDelay": 2,
                        "events": [{"description": "Lane closed", "code": 1}],
                        "delay": 120,
                        "length": 300,
                    },
                }
            ]
        },
        {
            "incidents": [
                {
                    "geometry": {"type": "Point", "coordinates": [-96.67, 33.10]},
                    "properties": {
                        "id": "dup-1",
                        "iconCategory": "1",
                        "magnitudeOfDelay": 2,
                        "events": [{"description": "Lane closed", "code": 1}],
                        "delay": 120,
                        "length": 300,
                    },
                },
                {
                    "geometry": {"type": "Point", "coordinates": [-123.04, 44.08]},
                    "properties": {
                        "id": "unique-2",
                        "iconCategory": "2",
                        "magnitudeOfDelay": 3,
                        "events": [{"description": "Construction", "code": 2}],
                        "delay": 60,
                        "length": 100,
                    },
                },
            ]
        },
    ]
    call_index = 0

    async def fake_request_json(_self, _method, _path, *, _params=None, **_kwargs):
        nonlocal call_index
        payload = payloads[min(call_index, len(payloads) - 1)]
        call_index += 1
        return payload

    monkeypatch.setattr(ProviderHTTPClient, "request_json", fake_request_json)

    provider = TomTomTrafficProvider()
    provider.api_key = "test-key"

    result = await provider.get_traffic(
        LayerQuery(
            path=GeoJSONLineString(
                coordinates=[(-96.6705, 33.1032), (-123.0463, 44.0860)]
            ),
            radius_meters=5000,
            limit=25,
        )
    )

    assert {incident.external_id for incident in result.incidents} == {
        "dup-1",
        "unique-2",
    }
    assert result.total_delay_seconds == 180


@pytest.mark.asyncio
async def test_get_traffic_rejects_radius_that_cannot_fit_provider_limit(
    monkeypatch: pytest.MonkeyPatch,
):
    called = False

    async def fake_request_json(_self, _method, _path, *, _params=None, **_kwargs):
        nonlocal called
        called = True
        return {"incidents": []}

    monkeypatch.setattr(ProviderHTTPClient, "request_json", fake_request_json)

    provider = TomTomTrafficProvider()
    provider.api_key = "test-key"

    with pytest.raises(
        ProviderBadRequestError,
        match="Traffic search radius is too large",
    ):
        await provider.get_traffic(
            LayerQuery(
                path=GeoJSONLineString(
                    coordinates=[(-96.6705, 33.1032), (-96.6705, 33.1032)]
                ),
                radius_meters=100_000,
                limit=25,
            )
        )

    assert called is False
