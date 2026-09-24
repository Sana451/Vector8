"""
Tests for the map overview HTTP endpoint.

Verifies partial degradation semantics: optional layer failures are reported in
``errors`` with HTTP 200, while a routing failure surfaces as HTTP 502.
"""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.geocoding.providers.tomtom import TomTomGeocodingProvider
from app.map.service import MapLayerService
from app.providers.exceptions import ProviderUnavailableError
from app.providers.here.poi import HerePoiProvider
from app.providers.schemas import TrafficLayerData
from app.providers.tomtom.traffic import TomTomTrafficProvider
from app.routing.exceptions import RoutingNoRouteFoundError
from app.routing.providers.tomtom import TomTomProvider

OVERVIEW_URL = "/api/v1/map/route-overview"

TOMTOM_ROUTE_RESPONSE = {
    "routes": [
        {
            "summary": {"lengthInMeters": 1200, "travelDurationInSeconds": 300},
            "legs": [
                {
                    "summary": {
                        "lengthInMeters": 1200,
                        "travelDurationInSeconds": 300,
                    },
                    "path": {
                        "type": "LineString",
                        "coordinates": [
                            [-74.006, 40.7128],
                            [-73.9855, 40.758],
                        ],
                    },
                }
            ],
        }
    ]
}


@pytest.fixture
def overview_payload() -> dict:
    """Minimal map overview request body."""
    return {
        "route": {
            "route_planning_locations": {
                "origin": {"type": "Point", "coordinates": [-74.006, 40.7128]},
                "destination": {"type": "Point", "coordinates": [-73.9855, 40.758]},
            }
        }
    }


class TestRouteOverviewEndpoint:
    """Aggregated endpoint behaviour."""

    def test_returns_route_and_reports_unconfigured_layers(
        self, client: TestClient, overview_payload: dict
    ):
        """Route succeeds while unconfigured layers degrade into errors."""
        with (
            patch.object(TomTomProvider, "calculate_route") as mock_route,
            patch.object(TomTomTrafficProvider, "get_traffic") as mock_traffic,
            patch.object(HerePoiProvider, "search_along_route") as mock_rest_areas,
        ):
            from app.routing.schemas import CalculateRouteResponse

            mock_route.return_value = CalculateRouteResponse.model_validate(
                TOMTOM_ROUTE_RESPONSE
            )
            mock_traffic.return_value = TrafficLayerData(provider="tomtom")
            mock_rest_areas.side_effect = ProviderUnavailableError(
                "HERE_API_KEY is not configured",
                provider="here",
            )

            response = client.post(
                OVERVIEW_URL,
                json=overview_payload,
                params={"force_refresh": "true"},
            )

        assert response.status_code == 200
        data = response.json()

        assert data["route"] is not None
        assert data["route"]["id"] is not None
        assert uuid.UUID(data["route"]["id"])
        assert data["route"]["provider"] == "tomtom"
        assert data["configured_providers"]["route"] == "tomtom"
        assert data["configured_providers"]["traffic"] == settings.TRAFFIC_PROVIDER
        assert data["configured_providers"]["fuel"] == settings.FUEL_PROVIDER
        assert len(data["route"]["routes"]) == 1

        if settings.TRAFFIC_PROVIDER == "off":
            assert data["traffic"] is not None
            assert data["traffic"]["provider"] == "off"
        else:
            assert data["traffic"] is not None
            assert data["traffic"]["provider"] == "tomtom"

        # Fuel and truck providers are intentionally unconfigured in tests.
        # Truck restrictions are intentionally unconfigured in tests.
        # Fuel/rest areas may either degrade or succeed depending on local provider config.
        failed_layers = {error["layer"] for error in data["errors"]}
        assert "truck_restrictions" in failed_layers
        assert isinstance(data["fuel_stations"], list)
        assert data["truck_restrictions"] == []
        assert data["rest_areas"]["type"] == "FeatureCollection"

    def test_layer_subset_limits_resolution(
        self, client: TestClient, overview_payload: dict
    ):
        """Requesting a subset skips the remaining layers."""
        overview_payload["layers"] = ["route", "fuel"]

        with patch.object(TomTomProvider, "calculate_route") as mock_route:
            from app.routing.schemas import CalculateRouteResponse

            mock_route.return_value = CalculateRouteResponse.model_validate(
                TOMTOM_ROUTE_RESPONSE
            )

            response = client.post(OVERVIEW_URL, json=overview_payload)

        assert response.status_code == 200
        data = response.json()

        failed_layers = {error["layer"] for error in data["errors"]}
        assert "truck_restrictions" not in failed_layers
        assert "rest_areas" not in failed_layers
        assert data["traffic"] is None

    def test_routing_failure_returns_502(
        self, client: TestClient, overview_payload: dict
    ):
        """A mandatory route failure aborts the request.

        ``force_refresh`` bypasses the persistent route cache so the mocked
        provider is guaranteed to be called.
        """
        with patch.object(TomTomProvider, "calculate_route") as mock_route:
            mock_route.side_effect = RoutingNoRouteFoundError(
                "No route found",
                provider="tomtom",
                provider_code="NO_ROUTE_FOUND",
            )

            response = client.post(
                OVERVIEW_URL,
                json=overview_payload,
                params={"force_refresh": "true"},
            )

        assert response.status_code == 502
        detail = response.json()["detail"]
        assert detail["message"] == "No route found"
        assert detail["provider"] == "tomtom"

    def test_invalid_coordinates_return_422(self, client: TestClient):
        """Coordinate validation happens before any provider call."""
        response = client.post(
            OVERVIEW_URL,
            json={
                "route": {
                    "route_planning_locations": {
                        "origin": {"type": "Point", "coordinates": [-200.0, 40.0]},
                        "destination": {
                            "type": "Point",
                            "coordinates": [-73.9855, 40.758],
                        },
                    }
                }
            },
        )

        assert response.status_code == 422

    def test_unexpected_service_error_returns_500(
        self, client: TestClient, overview_payload: dict
    ):
        """Unexpected map service errors are hidden behind HTTP 500."""
        with patch.object(MapLayerService, "get_overview") as mock_get_overview:
            mock_get_overview.side_effect = RuntimeError("boom")

            response = client.post(
                OVERVIEW_URL,
                json=overview_payload,
                params={"force_refresh": "true"},
            )

        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error"

    def test_accepts_address_payload(self, client: TestClient):
        """Modern request format supports free-form addresses."""
        payload = {
            "pickup": {"address": "1521 Hickory Trail Allen TX 75002"},
            "delivery": {"address": "3660 Gateway Street Springfield OR 97477"},
        }

        with (
            patch.object(TomTomGeocodingProvider, "search") as mock_geocode,
            patch.object(TomTomProvider, "calculate_route") as mock_route,
        ):
            from app.geocoding.schemas import GeocodingResult
            from app.providers.geo import GeoJSONPoint
            from app.routing.schemas import CalculateRouteResponse

            mock_geocode.side_effect = [
                GeocodingResult(
                    formatted_address="1521 Hickory Trail, Allen, TX 75002",
                    location=GeoJSONPoint(coordinates=(-96.6705, 33.1032)),
                ),
                GeocodingResult(
                    formatted_address="3660 Gateway Street, Springfield, OR 97477",
                    location=GeoJSONPoint(coordinates=(-123.0463, 44.0860)),
                ),
            ]
            mock_route.return_value = CalculateRouteResponse.model_validate(
                TOMTOM_ROUTE_RESPONSE
            )

            response = client.post(
                OVERVIEW_URL,
                json=payload,
                params={"force_refresh": "true"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["route"] is not None
        assert mock_geocode.call_count == 2

    def test_accepts_mixed_payload(self, client: TestClient):
        """Modern request format supports address + coordinate pairs."""
        payload = {
            "pickup": {"address": "1521 Hickory Trail Allen TX 75002"},
            "delivery": {
                "location": {
                    "type": "Point",
                    "coordinates": [-123.0463, 44.0860],
                }
            },
        }

        with (
            patch.object(TomTomGeocodingProvider, "search") as mock_geocode,
            patch.object(TomTomProvider, "calculate_route") as mock_route,
        ):
            from app.geocoding.schemas import GeocodingResult
            from app.providers.geo import GeoJSONPoint
            from app.routing.schemas import CalculateRouteResponse

            mock_geocode.return_value = GeocodingResult(
                formatted_address="1521 Hickory Trail, Allen, TX 75002",
                location=GeoJSONPoint(coordinates=(-96.6705, 33.1032)),
            )
            mock_route.return_value = CalculateRouteResponse.model_validate(
                TOMTOM_ROUTE_RESPONSE
            )

            response = client.post(
                OVERVIEW_URL,
                json=payload,
                params={"force_refresh": "true"},
            )

        assert response.status_code == 200
        assert mock_geocode.call_count == 1
