"""
Tests for the map overview HTTP endpoint.

Verifies partial degradation semantics: optional layer failures are reported in
``errors`` with HTTP 200, while a routing failure surfaces as HTTP 502.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.routing.exceptions import RoutingNoRouteFoundError

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
        with patch(
            "app.routing.providers.tomtom.TomTomProvider.calculate_route"
        ) as mock_route:
            from app.routing.schemas import CalculateRouteResponse

            mock_route.return_value = CalculateRouteResponse.model_validate(
                TOMTOM_ROUTE_RESPONSE
            )

            response = client.post(OVERVIEW_URL, json=overview_payload)

        assert response.status_code == 200
        data = response.json()

        assert data["route"] is not None
        assert data["route"]["provider"] == "tomtom"
        assert len(data["route"]["routes"]) == 1

        # Fuel and truck providers have no base URL configured in tests.
        failed_layers = {error["layer"] for error in data["errors"]}
        assert "fuel" in failed_layers
        assert "truck_restrictions" in failed_layers
        assert data["fuel_stations"] == []
        assert data["truck_restrictions"] == []

    def test_layer_subset_limits_resolution(
        self, client: TestClient, overview_payload: dict
    ):
        """Requesting a subset skips the remaining layers."""
        overview_payload["layers"] = ["route", "fuel"]

        with patch(
            "app.routing.providers.tomtom.TomTomProvider.calculate_route"
        ) as mock_route:
            from app.routing.schemas import CalculateRouteResponse

            mock_route.return_value = CalculateRouteResponse.model_validate(
                TOMTOM_ROUTE_RESPONSE
            )

            response = client.post(OVERVIEW_URL, json=overview_payload)

        assert response.status_code == 200
        data = response.json()

        failed_layers = {error["layer"] for error in data["errors"]}
        assert "truck_restrictions" not in failed_layers
        assert data["traffic"] is None

    def test_routing_failure_returns_502(
        self, client: TestClient, overview_payload: dict
    ):
        """A mandatory route failure aborts the request.

        ``force_refresh`` bypasses the persistent route cache so the mocked
        provider is guaranteed to be called.
        """
        with patch(
            "app.routing.providers.tomtom.TomTomProvider.calculate_route"
        ) as mock_route:
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
