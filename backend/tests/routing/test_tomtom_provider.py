"""
Tests for TomTom routing provider.

Tests HTTP communication, error handling, and request/response transformation.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.config import settings
from app.providers.tomtom.routing import TomTomRoutingProvider
from app.routing.exceptions import (
    RoutingAuthenticationError,
    RoutingNoRouteFoundError,
    RoutingRateLimitError,
    RoutingTimeoutError,
    RoutingUnavailableError,
)
from app.routing.schemas import (
    CalculateRouteRequest,
    GeoJSONPoint,
    RoutePlanningLocations,
)


@pytest.fixture
def basic_route_request():
    """Create basic route request for testing."""
    return CalculateRouteRequest(
        route_planning_locations=RoutePlanningLocations(
            origin=GeoJSONPoint(coordinates=[-74.006, 40.7128]),
            destination=GeoJSONPoint(coordinates=[-73.935, 40.7306]),
        )
    )


@pytest.fixture
def tomtom_success_response():
    """Load TomTom success response fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "tomtom_route_success.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def tomtom_error_response():
    """Load TomTom error response fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "tomtom_route_error.json"
    with open(fixture_path) as f:
        return json.load(f)


class TestTomTomProviderInit:
    """Test TomTom provider initialization."""

    @patch.object(settings, "TOMTOM_API_KEY", "fake-key-for-ci")
    @patch.object(settings, "TOMTOM_BASE_URL", "https://api.tomtom.com")
    @patch.object(settings, "TOMTOM_API_VERSION", "3")
    @patch.object(settings, "TOMTOM_TIMEOUT_SECONDS", 30)
    def test_init_with_defaults(self):
        """Test initialization with default settings."""
        provider = TomTomRoutingProvider()
        assert provider.api_key == "fake-key-for-ci"
        assert provider.base_url == "https://api.tomtom.com"
        assert provider.api_version == "3"
        assert provider.timeout == 30

    @patch.object(settings, "TOMTOM_API_KEY", "fake-key-for-ci")
    @patch.object(settings, "TOMTOM_BASE_URL", "https://api.tomtom.com")
    @patch.object(settings, "TOMTOM_API_VERSION", "3")
    @patch.object(settings, "TOMTOM_TIMEOUT_SECONDS", 30)
    def test_init_with_client(self):
        """Test initialization with provided client."""
        client = AsyncMock(spec=httpx.AsyncClient)
        provider = TomTomRoutingProvider(client=client)
        assert provider.client == client


class TestTomTomProviderRequestTransformation:
    """Test request transformation to TomTom format."""

    @patch.object(settings, "TOMTOM_API_KEY", "fake-key-for-ci")
    @patch.object(settings, "TOMTOM_BASE_URL", "https://api.tomtom.com")
    @patch.object(settings, "TOMTOM_API_VERSION", "3")
    @patch.object(settings, "TOMTOM_TIMEOUT_SECONDS", 30)
    def test_transform_basic_request(self, basic_route_request):
        """Test transformation of basic request."""
        provider = TomTomRoutingProvider()
        tomtom_request = provider._transform_request(basic_route_request)

        assert "routePlanningLocations" in tomtom_request
        assert "origin" in tomtom_request["routePlanningLocations"]
        assert "destination" in tomtom_request["routePlanningLocations"]

        origin = tomtom_request["routePlanningLocations"]["origin"]
        assert origin["type"] == "Point"
        assert origin["coordinates"] == [-74.006, 40.7128]

    @patch.object(settings, "TOMTOM_API_KEY", "fake-key-for-ci")
    @patch.object(settings, "TOMTOM_BASE_URL", "https://api.tomtom.com")
    @patch.object(settings, "TOMTOM_API_VERSION", "3")
    @patch.object(settings, "TOMTOM_TIMEOUT_SECONDS", 30)
    def test_transform_with_route_type(self):
        """Test transformation with route type."""
        provider = TomTomRoutingProvider()
        request = CalculateRouteRequest(
            route_planning_locations=RoutePlanningLocations(
                origin=GeoJSONPoint(coordinates=[0, 0]),
                destination=GeoJSONPoint(coordinates=[1, 1]),
            ),
            route_type="fast",
        )
        tomtom_request = provider._transform_request(request)
        assert tomtom_request["routeType"] == "fast"

    @patch.object(settings, "TOMTOM_API_KEY", "fake-key-for-ci")
    @patch.object(settings, "TOMTOM_BASE_URL", "https://api.tomtom.com")
    @patch.object(settings, "TOMTOM_API_VERSION", "3")
    @patch.object(settings, "TOMTOM_TIMEOUT_SECONDS", 30)
    def test_transform_with_traffic(self):
        """Test transformation with traffic mode."""
        provider = TomTomRoutingProvider()
        request = CalculateRouteRequest(
            route_planning_locations=RoutePlanningLocations(
                origin=GeoJSONPoint(coordinates=[0, 0]),
                destination=GeoJSONPoint(coordinates=[1, 1]),
            ),
            traffic="live",
        )
        tomtom_request = provider._transform_request(request)
        assert tomtom_request["traffic"] == "live"

    @patch.object(settings, "TOMTOM_API_KEY", "fake-key-for-ci")
    @patch.object(settings, "TOMTOM_BASE_URL", "https://api.tomtom.com")
    @patch.object(settings, "TOMTOM_API_VERSION", "3")
    @patch.object(settings, "TOMTOM_TIMEOUT_SECONDS", 30)
    def test_transform_with_vehicle_params(self):
        """Test transformation with vehicle parameters."""
        provider = TomTomRoutingProvider()
        request = CalculateRouteRequest(
            route_planning_locations=RoutePlanningLocations(
                origin=GeoJSONPoint(coordinates=[0, 0]),
                destination=GeoJSONPoint(coordinates=[1, 1]),
            ),
            vehicle_weight_in_kilograms=5000,
            vehicle_max_speed_in_kilometers_per_hour=100,
            vehicle_engine_type="combustion",
        )
        tomtom_request = provider._transform_request(request)
        assert tomtom_request["vehicleWeightInKilograms"] == 5000
        assert tomtom_request["vehicleMaxSpeedInKilometersPerHour"] == 100
        assert tomtom_request["vehicleEngineType"] == "combustion"


class TestTomTomProviderHeaders:
    """Test HTTP headers preparation."""

    @patch.object(settings, "TOMTOM_API_KEY", "fake-key-for-ci")
    @patch.object(settings, "TOMTOM_BASE_URL", "https://api.tomtom.com")
    @patch.object(settings, "TOMTOM_API_VERSION", "3")
    @patch.object(settings, "TOMTOM_TIMEOUT_SECONDS", 30)
    def test_prepare_headers_basic(self):
        """Test basic header preparation."""
        provider = TomTomRoutingProvider()
        request = CalculateRouteRequest(
            route_planning_locations=RoutePlanningLocations(
                origin=GeoJSONPoint(coordinates=[0, 0]),
                destination=GeoJSONPoint(coordinates=[1, 1]),
            )
        )
        headers = provider._prepare_headers(request, "test-tracking-id")

        assert headers["Content-Type"] == "application/json"
        assert headers["TomTom-Api-Key"] == "fake-key-for-ci"
        assert headers["TomTom-Api-Version"] == "3"
        assert headers["Tracking-ID"] == "test-tracking-id"

    @patch.object(settings, "TOMTOM_API_KEY", "fake-key-for-ci")
    @patch.object(settings, "TOMTOM_BASE_URL", "https://api.tomtom.com")
    @patch.object(settings, "TOMTOM_API_VERSION", "3")
    @patch.object(settings, "TOMTOM_TIMEOUT_SECONDS", 30)
    def test_prepare_headers_with_language(self):
        """Test header preparation with Accept-Language."""
        provider = TomTomRoutingProvider()
        request = CalculateRouteRequest(
            route_planning_locations=RoutePlanningLocations(
                origin=GeoJSONPoint(coordinates=[0, 0]),
                destination=GeoJSONPoint(coordinates=[1, 1]),
            ),
            accept_language="en-US",
        )
        headers = provider._prepare_headers(request, "test-tracking-id")
        assert headers["Accept-Language"] == "en-US"


class TestTomTomProviderCalculateRoute:
    """Test calculate_route method."""

    @pytest.mark.asyncio
    @patch.object(settings, "TOMTOM_API_KEY", "fake-key-for-ci")
    @patch.object(settings, "TOMTOM_BASE_URL", "https://api.tomtom.com")
    @patch.object(settings, "TOMTOM_API_VERSION", "3")
    @patch.object(settings, "TOMTOM_TIMEOUT_SECONDS", 30)
    async def test_calculate_route_success(
        self, basic_route_request, tomtom_success_response
    ):
        """Test successful route calculation."""
        provider = TomTomRoutingProvider()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = httpx.Headers()
        mock_response.json.return_value = tomtom_success_response

        with patch.object(httpx, "AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response

            result = await provider.calculate_route(basic_route_request)

            assert result is not None
            assert len(result.routes) > 0
            assert result.routes[0].summary.length_in_meters == 1234

    @pytest.mark.asyncio
    @patch.object(settings, "TOMTOM_API_KEY", "fake-key-for-ci")
    @patch.object(settings, "TOMTOM_BASE_URL", "https://api.tomtom.com")
    @patch.object(settings, "TOMTOM_API_VERSION", "3")
    @patch.object(settings, "TOMTOM_TIMEOUT_SECONDS", 30)
    async def test_calculate_route_with_provided_client(
        self, basic_route_request, tomtom_success_response
    ):
        """Test route calculation with provided client."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = httpx.Headers()
        mock_response.json.return_value = tomtom_success_response
        mock_client.post.return_value = mock_response

        provider = TomTomRoutingProvider(client=mock_client)
        result = await provider.calculate_route(basic_route_request)

        assert result is not None
        assert len(result.routes) > 0

    @pytest.mark.asyncio
    @patch.object(settings, "TOMTOM_API_KEY", "fake-key-for-ci")
    @patch.object(settings, "TOMTOM_BASE_URL", "https://api.tomtom.com")
    @patch.object(settings, "TOMTOM_API_VERSION", "3")
    @patch.object(settings, "TOMTOM_TIMEOUT_SECONDS", 30)
    async def test_calculate_route_timeout(self, basic_route_request):
        """Test timeout handling."""
        provider = TomTomRoutingProvider()
        with patch.object(httpx, "AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = httpx.TimeoutException("Timeout")

            with pytest.raises(RoutingTimeoutError):
                await provider.calculate_route(basic_route_request)

    @pytest.mark.asyncio
    @patch.object(settings, "TOMTOM_API_KEY", "fake-key-for-ci")
    @patch.object(settings, "TOMTOM_BASE_URL", "https://api.tomtom.com")
    @patch.object(settings, "TOMTOM_API_VERSION", "3")
    @patch.object(settings, "TOMTOM_TIMEOUT_SECONDS", 30)
    async def test_calculate_route_bad_request(
        self, basic_route_request, tomtom_error_response
    ):
        """Test 400 error handling."""
        provider = TomTomRoutingProvider()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.headers = httpx.Headers()
        mock_response.json.return_value = tomtom_error_response

        with patch.object(httpx, "AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response

            with pytest.raises(RoutingNoRouteFoundError):
                await provider.calculate_route(basic_route_request)

    @pytest.mark.asyncio
    @patch.object(settings, "TOMTOM_API_KEY", "fake-key-for-ci")
    @patch.object(settings, "TOMTOM_BASE_URL", "https://api.tomtom.com")
    @patch.object(settings, "TOMTOM_API_VERSION", "3")
    @patch.object(settings, "TOMTOM_TIMEOUT_SECONDS", 30)
    async def test_calculate_route_authentication_error(self, basic_route_request):
        """Test 403 authentication error handling."""
        provider = TomTomRoutingProvider()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 403
        mock_response.headers = httpx.Headers()
        mock_response.json.return_value = {"message": "Invalid API key"}

        with patch.object(httpx, "AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response

            with pytest.raises(RoutingAuthenticationError):
                await provider.calculate_route(basic_route_request)

    @pytest.mark.asyncio
    @patch.object(settings, "TOMTOM_API_KEY", "fake-key-for-ci")
    @patch.object(settings, "TOMTOM_BASE_URL", "https://api.tomtom.com")
    @patch.object(settings, "TOMTOM_API_VERSION", "3")
    @patch.object(settings, "TOMTOM_TIMEOUT_SECONDS", 30)
    async def test_calculate_route_rate_limit(self, basic_route_request):
        """Test 429 rate limit handling."""
        provider = TomTomRoutingProvider()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.headers = httpx.Headers()
        mock_response.json.return_value = {"message": "Rate limit exceeded"}

        with patch.object(httpx, "AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response

            with pytest.raises(RoutingRateLimitError):
                await provider.calculate_route(basic_route_request)

    @pytest.mark.asyncio
    @patch.object(settings, "TOMTOM_API_KEY", "fake-key-for-ci")
    @patch.object(settings, "TOMTOM_BASE_URL", "https://api.tomtom.com")
    @patch.object(settings, "TOMTOM_API_VERSION", "3")
    @patch.object(settings, "TOMTOM_TIMEOUT_SECONDS", 30)
    async def test_calculate_route_unavailable(self, basic_route_request):
        """Test 503 unavailable error handling."""
        provider = TomTomRoutingProvider()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 503
        mock_response.headers = httpx.Headers()
        mock_response.json.return_value = {"message": "Service unavailable"}

        with patch.object(httpx, "AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response

            with pytest.raises(RoutingUnavailableError):
                await provider.calculate_route(basic_route_request)
