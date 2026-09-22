"""Tests for the HERE fuel provider."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

import app.providers.fuel.here as here_module
from app.core.config import settings
from app.providers.exceptions import (
    ProviderBadRequestError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)
from app.providers.fuel.here import HereFuelProvider
from app.providers.fuel.off import OffFuelProvider
from app.providers.geo import GeoJSONLineString
from app.providers.http import ProviderHTTPClient
from app.providers.schemas import LayerQuery


@pytest.fixture
def layer_query() -> LayerQuery:
    return LayerQuery(
        path=GeoJSONLineString(
            coordinates=[
                (-87.90, 41.80),
                (-87.80, 41.85),
                (-87.70, 41.90),
            ]
        ),
        radius_meters=9000,
        limit=250,
    )


@pytest.mark.asyncio
async def test_find_stations_calls_here_with_truck_diesel_params(
    monkeypatch: pytest.MonkeyPatch,
    layer_query: LayerQuery,
):
    recorded_calls: list[dict[str, Any]] = []

    async def fake_request_json(
        _self, method, path, *, params=None, json=None, **_kwargs
    ):
        recorded_calls.append(
            {"method": method, "path": path, "params": params, "json": json}
        )
        return {"stations": []}

    monkeypatch.setattr(ProviderHTTPClient, "request_json", fake_request_json)

    provider = HereFuelProvider()
    provider.api_key = "test-key"
    stations = await provider.find_stations(layer_query)

    assert stations == []
    assert len(recorded_calls) == 1
    call = recorded_calls[0]
    assert call["method"] == "POST"
    assert call["path"] == "/v3/stations"
    assert call["params"] == {
        "apiKey": "test-key",
        "fuelTypes": "11",
        "limit": min(layer_query.limit, settings.HERE_FUEL_LIMIT),
        "sort": "price:asc",
        "returnAllStations": "true",
    }
    assert call["json"] == {
        "corridor": [
            {"lat": 41.8, "lng": -87.9},
            {"lat": 41.85, "lng": -87.8},
            {"lat": 41.9, "lng": -87.7},
        ],
        "width": min(layer_query.radius_meters, settings.HERE_FUEL_CORRIDOR_WIDTH),
    }


@pytest.mark.asyncio
async def test_find_stations_simplifies_large_corridor_before_request(
    monkeypatch: pytest.MonkeyPatch,
):
    recorded_calls: list[dict[str, Any]] = []
    coordinates = [
        (-88.0 + index * 0.001, 41.0 + index * 0.001) for index in range(220)
    ]

    async def fake_request_json(
        _self, method, path, *, params=None, json=None, **_kwargs
    ):
        recorded_calls.append(
            {"method": method, "path": path, "params": params, "json": json}
        )
        return {"stations": []}

    monkeypatch.setattr(ProviderHTTPClient, "request_json", fake_request_json)

    provider = HereFuelProvider()
    provider.api_key = "test-key"
    await provider.find_stations(
        LayerQuery(
            path=GeoJSONLineString(coordinates=coordinates),
            radius_meters=5000,
            limit=50,
        )
    )

    assert len(recorded_calls) == 1
    corridor = recorded_calls[0]["json"]["corridor"]
    assert len(corridor) < len(coordinates)
    assert len(corridor) <= 100
    assert corridor[0] == {"lat": coordinates[0][1], "lng": coordinates[0][0]}
    assert corridor[-1] == {"lat": coordinates[-1][1], "lng": coordinates[-1][0]}


@pytest.mark.asyncio
async def test_find_stations_normalizes_here_payload(
    monkeypatch: pytest.MonkeyPatch,
    layer_query: LayerQuery,
):
    async def fake_request_json(_self, _method, _path, **_kwargs):
        return {
            "stations": [
                {
                    "id": "station-1",
                    "name": "Pilot Flying J",
                    "brand": "Pilot",
                    "location": {"lat": 41.88978, "lng": -87.74529},
                    "address": {"label": "123 Truck Stop Rd, Chicago, IL"},
                    "distance": 1934,
                    "truckAccessible": True,
                    "openingHours": [{"isOpen": True, "text": ["Open 24/7"]}],
                    "contacts": [
                        {
                            "phone": [{"value": "+13125550123"}],
                            "www": [{"value": "https://pilot.example.com"}],
                        }
                    ],
                    "fuels": [
                        {"fuelType": 11, "price": 3.59, "currency": "USD"},
                        {"fuelType": 72, "price": 0.99, "currency": "USD"},
                    ],
                }
            ]
        }

    monkeypatch.setattr(ProviderHTTPClient, "request_json", fake_request_json)

    provider = HereFuelProvider()
    provider.api_key = "test-key"
    stations = await provider.find_stations(layer_query)

    assert len(stations) == 1
    station = stations[0]
    assert station.external_id == "station-1"
    assert station.name == "Pilot Flying J"
    assert station.brand == "Pilot"
    assert station.address == "123 Truck Stop Rd, Chicago, IL"
    assert station.location.coordinates == (-87.74529, 41.88978)
    assert station.diesel_price == pytest.approx(3.59)
    assert station.currency == "USD"
    assert station.fuel_type == "Truck Diesel"
    assert station.distance_meters == pytest.approx(1934)
    assert station.is_open is True
    assert station.phone == "+13125550123"
    assert station.website == "https://pilot.example.com"
    assert station.has_adblue is True
    assert station.truck_accessible is True
    assert station.opening_hours == [{"isOpen": True, "text": ["Open 24/7"]}]


@pytest.mark.asyncio
async def test_find_stations_keeps_station_without_price_when_return_all_enabled(
    monkeypatch: pytest.MonkeyPatch,
    layer_query: LayerQuery,
):
    async def fake_request_json(_self, _method, _path, **_kwargs):
        return {
            "stations": [
                {
                    "id": "station-2",
                    "name": "Love's Travel Stop",
                    "location": {"lat": 41.7, "lng": -87.6},
                    "fuels": [{"fuelType": 72, "price": 1.05, "currency": "USD"}],
                }
            ]
        }

    monkeypatch.setattr(ProviderHTTPClient, "request_json", fake_request_json)

    provider = HereFuelProvider()
    provider.api_key = "test-key"
    stations = await provider.find_stations(layer_query)

    assert len(stations) == 1
    station = stations[0]
    assert station.diesel_price is None
    assert station.currency is None
    assert station.has_adblue is True
    assert station.is_open is None


@pytest.mark.asyncio
async def test_find_stations_normalizes_current_here_v3_payload(
    monkeypatch: pytest.MonkeyPatch,
    layer_query: LayerQuery,
):
    async def fake_request_json(_self, _method, _path, **_kwargs):
        return {
            "stations": [
                {
                    "id": "station-3",
                    "name": "LOVE'S",
                    "brand": "Love's",
                    "position": {"lat": 38.09573, "lng": -102.61981},
                    "access": {"lat": 38.09573, "lng": -102.61981},
                    "address": {
                        "label": "Loves Travel Stop [605 N Main St], Lamar, 81052"
                    },
                    "open24x7": True,
                    "contacts": {
                        "phones": [{"value": "+17193365202", "label": "PHONE"}],
                        "faxes": [{"value": "+17193365202", "label": "FAX"}],
                    },
                    "prices": [
                        {
                            "price": 6.169,
                            "deltaPrice": 0,
                            "indexScore": 5,
                            "fuelType": "11",
                            "unit": "gal",
                            "currency": "USD",
                        },
                        {
                            "price": 0.999,
                            "fuelType": 72,
                            "unit": "gal",
                            "currency": "USD",
                        },
                    ],
                    "stationDetails": {
                        "openingHours": {
                            "regularSchedule": [
                                {
                                    "days": [
                                        "mo",
                                        "tu",
                                        "we",
                                        "th",
                                        "fr",
                                        "sa",
                                        "su",
                                    ],
                                    "periods": [{"from": "00:00:00", "to": "24:00:00"}],
                                }
                            ]
                        },
                        "restrictedAccess": False,
                        "accessibilities": [
                            "Suitable for cars",
                            "Suitable for medium trucks",
                            "Suitable for large trucks",
                        ],
                    },
                }
            ]
        }

    monkeypatch.setattr(ProviderHTTPClient, "request_json", fake_request_json)

    provider = HereFuelProvider()
    provider.api_key = "test-key"
    stations = await provider.find_stations(layer_query)

    assert len(stations) == 1
    station = stations[0]
    assert station.external_id == "station-3"
    assert station.name == "LOVE'S"
    assert station.brand == "Love's"
    assert station.address == "Loves Travel Stop [605 N Main St], Lamar, 81052"
    assert station.location.coordinates == (-102.61981, 38.09573)
    assert station.diesel_price == pytest.approx(6.169)
    assert station.currency == "USD"
    assert station.is_open is True
    assert station.opening_hours == [
        {
            "regularSchedule": [
                {
                    "days": ["mo", "tu", "we", "th", "fr", "sa", "su"],
                    "periods": [{"from": "00:00:00", "to": "24:00:00"}],
                }
            ]
        }
    ]
    assert station.phone == "+17193365202"
    assert station.website is None
    assert station.has_adblue is True
    assert station.truck_accessible is True


@pytest.mark.asyncio
async def test_find_stations_logs_raw_payload_and_pagination_hints(
    monkeypatch: pytest.MonkeyPatch,
    layer_query: LayerQuery,
):
    logged_info: list[tuple[str, dict[str, Any]]] = []
    logged_warnings: list[tuple[str, dict[str, Any]]] = []
    payload = {
        "stations": [
            {
                "id": "station-page-1",
                "name": "Pilot",
                "position": {"lat": 41.7, "lng": -87.6},
                "prices": [{"fuelType": "11", "price": 4.25, "currency": "USD"}],
            }
        ],
        "hasMore": True,
        "offset": 0,
        "limit": 200,
        "nextPageToken": "page-2-token",
    }

    async def fake_request_json(_self, _method, _path, **_kwargs):
        return payload

    def fake_info(message: str, **kwargs: Any):
        logged_info.append((message, kwargs))

    def fake_warning(message: str, **kwargs: Any):
        logged_warnings.append((message, kwargs))

    monkeypatch.setattr(ProviderHTTPClient, "request_json", fake_request_json)
    monkeypatch.setattr(here_module.logger, "info", fake_info)
    monkeypatch.setattr(here_module.logger, "warning", fake_warning)

    provider = HereFuelProvider()
    provider.api_key = "test-key"
    stations = await provider.find_stations(layer_query)

    assert len(stations) == 1
    raw_response_logs = [
        kwargs
        for message, kwargs in logged_info
        if message == "HERE fuel raw response payload"
    ]
    assert len(raw_response_logs) == 1
    assert raw_response_logs[0]["payload"] == payload
    assert raw_response_logs[0]["items_key"] == "stations"
    assert raw_response_logs[0]["items_count"] == 1
    assert raw_response_logs[0]["pagination"] == {
        "hasMore": True,
        "offset": 0,
        "limit": 200,
        "nextPageToken": "page-2-token",
    }

    pagination_warnings = [
        kwargs
        for message, kwargs in logged_warnings
        if message == "HERE fuel response may be paginated or truncated"
    ]
    assert len(pagination_warnings) == 1
    assert pagination_warnings[0]["pagination"]["hasMore"] is True
    assert pagination_warnings[0]["pagination"]["nextPageToken"] == "page-2-token"


@pytest.mark.asyncio
async def test_find_stations_infers_not_truck_accessible_for_cars_only_here_v3_payload(
    monkeypatch: pytest.MonkeyPatch,
    layer_query: LayerQuery,
):
    async def fake_request_json(_self, _method, _path, **_kwargs):
        return {
            "stations": [
                {
                    "id": "station-4",
                    "name": "SUNOCO",
                    "position": {"lat": 34.2922, "lng": -99.7552},
                    "open24x7": True,
                    "contacts": {
                        "phones": [{"value": "+18777983752", "label": "PHONE"}]
                    },
                    "stationDetails": {
                        "openingHours": {
                            "regularSchedule": [
                                {
                                    "days": [
                                        "mo",
                                        "tu",
                                        "we",
                                        "th",
                                        "fr",
                                        "sa",
                                        "su",
                                    ],
                                    "periods": [{"from": "00:00:00", "to": "24:00:00"}],
                                }
                            ]
                        },
                        "restrictedAccess": False,
                        "accessibilities": ["Suitable for cars"],
                    },
                }
            ]
        }

    monkeypatch.setattr(ProviderHTTPClient, "request_json", fake_request_json)

    provider = HereFuelProvider()
    provider.api_key = "test-key"
    stations = await provider.find_stations(layer_query)

    assert len(stations) == 1
    station = stations[0]
    assert station.phone == "+18777983752"
    assert station.diesel_price is None
    assert station.is_open is True
    assert station.truck_accessible is False


@pytest.mark.asyncio
async def test_find_stations_raises_when_here_api_key_missing(layer_query: LayerQuery):
    provider = HereFuelProvider()
    provider.api_key = None

    with pytest.raises(ProviderUnavailableError) as exc_info:
        await provider.find_stations(layer_query)

    assert exc_info.value.provider == "here"


@pytest.mark.asyncio
async def test_find_stations_propagates_rate_limit_error(layer_query: LayerQuery):
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(429, json={"message": "too many requests"})
        )
    )
    provider = HereFuelProvider(client=client)
    provider.api_key = "test-key"

    try:
        with pytest.raises(ProviderRateLimitError):
            await provider.find_stations(layer_query)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_find_stations_propagates_server_unavailable(layer_query: LayerQuery):
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(500, json={"message": "temporary failure"})
        )
    )
    provider = HereFuelProvider(client=client)
    provider.api_key = "test-key"

    try:
        with pytest.raises(ProviderUnavailableError):
            await provider.find_stations(layer_query)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_find_stations_maps_413_to_clean_bad_request(layer_query: LayerQuery):
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                413,
                text="<html><body>Request Entity Too Large</body></html>",
                headers={"content-type": "text/html"},
            )
        )
    )
    provider = HereFuelProvider(client=client)
    provider.api_key = "test-key"

    try:
        with pytest.raises(ProviderBadRequestError) as exc_info:
            await provider.find_stations(layer_query)
    finally:
        await client.aclose()

    assert exc_info.value.provider == "here"
    assert exc_info.value.status_code == 413
    assert "too large" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_off_fuel_provider_returns_empty_list(layer_query: LayerQuery):
    provider = OffFuelProvider()

    assert await provider.find_stations(layer_query) == []
