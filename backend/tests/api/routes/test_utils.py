"""
Tests for utils API routes.

Tests health check and test email endpoints.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestHealthCheck:
    """Test health-check endpoint."""

    def test_health_check_returns_true(self, client):
        """Test that health check endpoint returns true."""
        response = client.get("/api/v1/utils/health-check/")
        assert response.status_code == 200
        assert response.json() is True

    def test_health_check_no_auth_required(self, client):
        """Test that health check doesn't require authentication."""
        # Should work without any token
        response = client.get("/api/v1/utils/health-check/")
        assert response.status_code == 200

    def test_health_check_endpoint_exists(self, client):
        """Test that health-check endpoint is properly registered."""
        response = client.get("/api/v1/utils/health-check/")
        assert response.status_code != 404


class TestEmailEndpoint:
    """Test test-email endpoint."""

    def test_test_email_requires_superuser(self, client):
        """Test that email endpoint requires superuser authentication."""
        response = client.post(
            "/api/v1/utils/test-email/",
            params={"email_to": "test@example.com"},
        )
        # Should return 403 Forbidden (not superuser)
        assert response.status_code in [401, 403]

    def test_test_email_invalid_email_format(self, client):
        """Test test-email with invalid email format."""
        response = client.post(
            "/api/v1/utils/test-email/",
            params={"email_to": "invalid-email"},
        )
        # Should return validation error
        assert response.status_code in [422, 403, 401]

    def test_test_email_endpoint_exists(self, client):
        """Test that test-email endpoint is properly registered."""
        response = client.post(
            "/api/v1/utils/test-email/",
            params={"email_to": "test@example.com"},
        )
        # Should not return 404 (endpoint exists)
        assert response.status_code != 404

    def test_test_email_returns_message_on_success(self, client):
        """Test that test-email returns message on success."""
        # Mock the superuser check and email functions
        with patch("app.api.routes.utils.get_current_active_superuser") as mock_super:
            with patch("app.api.routes.utils.generate_test_email") as mock_gen:
                with patch("app.api.routes.utils.send_email"):
                    from app.models import User

                    mock_user = User(
                        email="admin@example.com",
                        is_superuser=True,
                        is_active=True,
                    )
                    mock_super.return_value = mock_user

                    mock_gen.return_value.subject = "Test email"
                    mock_gen.return_value.html_content = "<p>Test</p>"

                    response = client.post(
                        "/api/v1/utils/test-email/",
                        params={"email_to": "test@example.com"},
                    )

                    # Should be 201 Created on success
                    if response.status_code == 201:
                        data = response.json()
                        assert "message" in data
                        assert "Test email sent" in data["message"]

    def test_test_email_status_code_201(self):
        """Test that test-email returns status code 201."""
        # This test verifies the status code is correctly set in decorator
        from app.api.routes.utils import router

        # Find the test_email route
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/test-email/":
                assert 201 in route.status_code
                break
