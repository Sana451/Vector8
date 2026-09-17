"""
Tests for routing API router.

Tests HTTP API endpoints and request/response handling.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def tomtom_success_response():
    """Load TomTom success response fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "tomtom_route_success.json"
    with open(fixture_path) as f:
        return json.load(f)


class TestCalculateRouteEndpoint:
    """Test POST /api/v1/routing/routes/calculate endpoint."""

    def test_calculate_route_basic_request(self, client, tomtom_success_response):
        """Test basic route calculation request."""
        request_body = {
            "route_planning_locations": {
                "origin": {
                    "type": "Point",
                    "coordinates": [-74.006, 40.7128],
                },
                "destination": {
                    "type": "Point",
                    "coordinates": [-73.935, 40.7306],
                },
            },
        }

        with patch(
            "app.routing.providers.tomtom.TomTomProvider.calculate_route"
        ) as mock_calculate:
            from app.routing.schemas import CalculateRouteResponse

            mock_response = CalculateRouteResponse.model_validate(
                tomtom_success_response
            )
            mock_calculate.return_value = mock_response

            response = client.post(
                "/api/v1/routing/routes/calculate", json=request_body
            )
            assert response.status_code == 200
            data = response.json()
            assert "routes" in data
            assert len(data["routes"]) > 0

    def test_calculate_route_with_waypoints(self, client, tomtom_success_response):
        """Test route calculation with waypoints."""
        request_body = {
            "route_planning_locations": {
                "origin": {
                    "type": "Point",
                    "coordinates": [-74.006, 40.7128],
                },
                "destination": {
                    "type": "Point",
                    "coordinates": [-73.935, 40.7306],
                },
                "waypoints": {
                    "type": "MultiPoint",
                    "coordinates": [
                        [-74.00, 40.72],
                        [-73.95, 40.73],
                    ],
                },
            },
        }

        with patch(
            "app.routing.providers.tomtom.TomTomProvider.calculate_route"
        ) as mock_calculate:
            from app.routing.schemas import CalculateRouteResponse

            mock_response = CalculateRouteResponse.model_validate(
                tomtom_success_response
            )
            mock_calculate.return_value = mock_response

            response = client.post(
                "/api/v1/routing/routes/calculate", json=request_body
            )
            assert response.status_code == 200

    def test_calculate_route_with_options(self, client, tomtom_success_response):
        """Test route calculation with various options."""
        request_body = {
            "route_planning_locations": {
                "origin": {
                    "type": "Point",
                    "coordinates": [-74.006, 40.7128],
                },
                "destination": {
                    "type": "Point",
                    "coordinates": [-73.935, 40.7306],
                },
            },
            "route_type": "fast",
            "traffic": "live",
            "vehicle_engine_type": "combustion",
            "vehicle_weight_in_kilograms": 5000,
            "vehicle_max_speed_in_kilometers_per_hour": 100,
        }

        with patch(
            "app.routing.providers.tomtom.TomTomProvider.calculate_route"
        ) as mock_calculate:
            from app.routing.schemas import CalculateRouteResponse

            mock_response = CalculateRouteResponse.model_validate(
                tomtom_success_response
            )
            mock_calculate.return_value = mock_response

            response = client.post(
                "/api/v1/routing/routes/calculate", json=request_body
            )
            assert response.status_code == 200

    def test_calculate_route_invalid_coordinates(self, client):
        """Test request with invalid coordinates."""
        request_body = {
            "route_planning_locations": {
                "origin": {
                    "type": "Point",
                    "coordinates": [200, 40.7128],  # Invalid longitude
                },
                "destination": {
                    "type": "Point",
                    "coordinates": [-73.935, 40.7306],
                },
            },
        }

        response = client.post("/api/v1/routing/routes/calculate", json=request_body)
        assert response.status_code == 422  # Validation error

    def test_calculate_route_missing_origin(self, client):
        """Test request missing origin."""
        request_body = {
            "route_planning_locations": {
                "destination": {
                    "type": "Point",
                    "coordinates": [-73.935, 40.7306],
                },
            },
        }

        response = client.post("/api/v1/routing/routes/calculate", json=request_body)
        assert response.status_code == 422  # Validation error

    def test_calculate_route_missing_destination(self, client):
        """Test request missing destination."""
        request_body = {
            "route_planning_locations": {
                "origin": {
                    "type": "Point",
                    "coordinates": [-74.006, 40.7128],
                },
            },
        }

        response = client.post("/api/v1/routing/routes/calculate", json=request_body)
        assert response.status_code == 422  # Validation error

    def test_calculate_route_empty_avoids_list(self, client):
        """Test request with empty avoids list."""
        request_body = {
            "route_planning_locations": {
                "origin": {
                    "type": "Point",
                    "coordinates": [-74.006, 40.7128],
                },
                "destination": {
                    "type": "Point",
                    "coordinates": [-73.935, 40.7306],
                },
            },
            "avoids": [],  # Empty list should be rejected
        }

        response = client.post("/api/v1/routing/routes/calculate", json=request_body)
        assert response.status_code == 422  # Validation error

    def test_endpoint_exists(self, client):
        """Test that endpoint exists and has correct path."""
        # This test just verifies the endpoint is registered
        # A proper request should return either 200 or 422 (validation), not 404
        request_body = {
            "route_planning_locations": {
                "origin": {
                    "type": "Point",
                    "coordinates": [-74.006, 40.7128],
                },
                "destination": {
                    "type": "Point",
                    "coordinates": [-73.935, 40.7306],
                },
            },
        }

        with patch(
            "app.routing.providers.tomtom.TomTomProvider.calculate_route"
        ) as mock_calculate:
            from app.routing.schemas import CalculateRouteResponse

            # Create a minimal success response
            mock_response = CalculateRouteResponse(
                routes=[
                    {
                        "summary": {
                            "length_in_meters": 100,
                            "travel_duration_in_seconds": 60,
                        }
                    }
                ]
            )
            mock_calculate.return_value = mock_response

            response = client.post(
                "/api/v1/routing/routes/calculate", json=request_body
            )
            assert response.status_code != 404
