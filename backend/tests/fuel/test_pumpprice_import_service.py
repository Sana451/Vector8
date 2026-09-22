from __future__ import annotations

import httpx
import pytest
from sqlmodel import Session, delete, select

import app.fuel.service as pumpprice_module
from app.fuel.schemas import PumpPriceImportRequest
from app.fuel.service import PumpPriceImportService
from app.map.models import FuelStation
from app.map.repository import FuelStationRepository
from app.providers.http import ProviderHTTPClient


@pytest.mark.asyncio
async def test_pumpprice_import_deduplicates_and_persists(
    monkeypatch: pytest.MonkeyPatch,
    db: Session,
):
    db.exec(delete(FuelStation))
    db.commit()

    recorded_cookies: list[str] = []

    async def fake_request_json(
        _self,
        _method,
        _path,
        *,
        params=None,
        headers=None,
        **_kwargs,
    ):
        assert params is not None
        assert headers is not None
        recorded_cookies.append(headers["Cookie"])
        assert params == {
            "miles": 2000,
            "lat": 39.8283,
            "lng": -98.5795,
        }
        assert (
            _self.default_headers["accept-language"]
            == "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
        )
        assert _self.default_headers["priority"] == "u=1, i"
        assert _self.default_headers["sec-ch-ua-mobile"] == "?0"
        assert _self.default_headers["sec-fetch-site"] == "same-origin"
        return {
            "result": {
                "fuel_prices": [
                    {
                        "id": 1,
                        "remote_id": "alpha",
                        "store_name": "Love's #226",
                        "store_code": "LV",
                        "street": "6470 N Elizabeth St",
                        "city": "Pueblo",
                        "state": "CO",
                        "latitude": 38.3375,
                        "longitude": -104.6238,
                        "discounted_price": 5.87,
                        "retail_price": 6.389,
                        "distance": 14.2,
                        "updated_at": "2026-09-21T08:44:51.754-05:00",
                    },
                    {
                        "id": 1,
                        "remote_id": "alpha",
                        "store_name": "Love's #226",
                        "store_code": "LV",
                        "street": "6470 N Elizabeth St",
                        "city": "Pueblo",
                        "state": "CO",
                        "latitude": 38.3375,
                        "longitude": -104.6238,
                        "discounted_price": 5.92,
                        "retail_price": 6.389,
                        "distance": 12.5,
                        "updated_at": "2026-09-22T08:44:51.754-05:00",
                    },
                    {
                        "id": 2,
                        "remote_id": "beta",
                        "store_name": "Maverik Pueblo 734",
                        "store_code": "MV",
                        "street": "1001 W Pueblo Blvd",
                        "city": "Pueblo",
                        "state": "CO",
                        "latitude": 38.2187,
                        "longitude": -104.6256,
                        "discounted_price": 5.95,
                        "retail_price": 6.199,
                        "distance": 17.7,
                        "updated_at": "2026-09-22T07:44:35.975-05:00",
                    },
                ]
            },
            "status": "Success",
            "error_messages": None,
        }

    monkeypatch.setattr(ProviderHTTPClient, "request_json", fake_request_json)

    service = PumpPriceImportService(FuelStationRepository(db))
    response = await service.import_prices(
        PumpPriceImportRequest(fuel_analytics_session="cookie-value")
    )

    rows = db.exec(select(FuelStation).where(FuelStation.provider == "internal")).all()

    assert recorded_cookies == ["_fuel_analytics_session=cookie-value"]
    assert response.stations_received == 3
    assert response.unique_stations == 2
    assert response.duplicates_discarded == 1
    assert response.persisted_stations == 2
    assert len(rows) == 2
    assert {row.external_id for row in rows} == {"pumpprice:alpha", "pumpprice:beta"}

    alpha = next(row for row in rows if row.external_id == "pumpprice:alpha")
    assert alpha.diesel_price == pytest.approx(5.92)

    db.exec(delete(FuelStation))
    db.commit()


def test_pumpprice_error_logging_sanitizes_cookie(monkeypatch: pytest.MonkeyPatch):
    service = PumpPriceImportService(
        repository=FuelStationRepository.__new__(FuelStationRepository)
    )
    logged: list[tuple[str, dict[str, object]]] = []

    def fake_error(event: str, **kwargs):
        logged.append((event, kwargs))

    monkeypatch.setattr(pumpprice_module.logger, "error", fake_error)

    request = httpx.Request(
        "GET",
        "https://www.pumpprice.co/account/fuel_maps/fuel_prices?miles=1700&lat=39.8283&lng=-98.5795",
        headers={
            "cookie": "_fuel_analytics_session=secret",
            "accept": "application/json",
        },
    )
    response = httpx.Response(
        401,
        request=request,
        headers={"set-cookie": "session=secret", "content-type": "application/json"},
        json={"error": "unauthorized"},
    )

    service._log_error_response(response)

    assert len(logged) == 1
    event, payload = logged[0]
    assert event == "PumpPrice provider returned error response"
    assert payload["status_code"] == 401
    assert payload["request_headers"]["cookie"] == "<redacted>"
    assert payload["response_headers"]["set-cookie"] == "<redacted>"
    assert payload["response_json"] == {"error": "unauthorized"}
