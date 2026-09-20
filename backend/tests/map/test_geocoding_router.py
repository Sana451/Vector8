"""Tests for the public geocoding endpoint."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.geocoding.providers.tomtom import TomTomGeocodingProvider

GEOCODING_URL = "/api/v1/geocoding/search"


def test_geocoding_search_returns_normalized_point(client: TestClient):
    """Public geocoding endpoint returns formatted address and coordinates."""
    with patch.object(TomTomGeocodingProvider, "search") as mock_search:
        from app.geocoding.schemas import GeocodingResult
        from app.providers.geo import GeoJSONPoint

        mock_search.return_value = GeocodingResult(
            formatted_address="1521 Hickory Trail, Allen, TX 75002",
            location=GeoJSONPoint(coordinates=(-96.6705, 33.1032)),
            provider_id="tt-1",
        )

        response = client.post(
            GEOCODING_URL,
            json={"query": "1521 Hickory Trail Allen TX 75002"},
            params={"force_refresh": "true"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "formatted_address": "1521 Hickory Trail, Allen, TX 75002",
        "location": {
            "type": "Point",
            "coordinates": [-96.6705, 33.1032],
        },
    }
