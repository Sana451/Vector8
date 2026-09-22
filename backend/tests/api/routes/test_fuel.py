from __future__ import annotations

from fastapi.testclient import TestClient

from app.fuel.schemas import PumpPriceImportResponse
from app.fuel.service import PumpPriceImportService
from app.providers.exceptions import (
    ProviderAuthenticationError,
    ProviderUnavailableError,
)


def test_pumpprice_import_requires_superuser(client: TestClient) -> None:
    response = client.post(
        "/api/v1/fuel/import/pumpprice",
        json={"fuel_analytics_session": "cookie"},
    )

    assert response.status_code in (401, 403)


def test_pumpprice_import_runs_for_superuser(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    monkeypatch,
) -> None:
    async def fake_import_prices(_self, request):
        assert request.fuel_analytics_session == "cookie"
        return PumpPriceImportResponse(
            stations_received=12,
            unique_stations=11,
            duplicates_discarded=1,
            persisted_stations=11,
        )

    monkeypatch.setattr(PumpPriceImportService, "import_prices", fake_import_prices)

    response = client.post(
        "/api/v1/fuel/import/pumpprice",
        json={"fuel_analytics_session": "cookie"},
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    assert response.json()["persisted_provider"] == "internal"
    assert response.json()["persisted_stations"] == 11


def test_pumpprice_import_maps_invalid_session_to_401(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    monkeypatch,
) -> None:
    async def fake_import_prices(_self, _request):
        raise ProviderAuthenticationError(
            "PumpPrice session is invalid or expired; provide a fresh _fuel_analytics_session cookie",
            provider="pumpprice",
            status_code=401,
        )

    monkeypatch.setattr(PumpPriceImportService, "import_prices", fake_import_prices)

    response = client.post(
        "/api/v1/fuel/import/pumpprice",
        json={"fuel_analytics_session": "cookie"},
        headers=superuser_token_headers,
    )

    assert response.status_code == 401
    assert response.json()["detail"]["provider"] == "pumpprice"
    assert "invalid or expired" in response.json()["detail"]["message"]


def test_pumpprice_import_maps_provider_failure_to_502(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    monkeypatch,
) -> None:
    async def fake_import_prices(_self, _request):
        raise ProviderUnavailableError(
            "PumpPrice temporarily unavailable",
            provider="pumpprice",
            status_code=503,
        )

    monkeypatch.setattr(PumpPriceImportService, "import_prices", fake_import_prices)

    response = client.post(
        "/api/v1/fuel/import/pumpprice",
        json={"fuel_analytics_session": "cookie"},
        headers=superuser_token_headers,
    )

    assert response.status_code == 502
    assert response.json()["detail"]["provider"] == "pumpprice"
    assert response.json()["detail"]["message"] == "PumpPrice temporarily unavailable"
