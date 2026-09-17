"""
Tests for routing utilities.

Tests coordinate validation, tracking ID generation, headers building, etc.
"""

import pytest

from app.routing.utils import (
    build_attributes_header,
    generate_tracking_id,
    mask_api_key,
    validate_coordinates,
    validate_tracking_id,
)


class TestValidateCoordinates:
    """Test validate_coordinates function."""

    def test_valid_coordinates(self):
        """Test validation with valid coordinates."""
        lon, lat = validate_coordinates(-74.006, 40.7128)
        assert lon == -74.006
        assert lat == 40.7128

    def test_valid_coordinates_zero(self):
        """Test validation with zero coordinates."""
        lon, lat = validate_coordinates(0.0, 0.0)
        assert lon == 0.0
        assert lat == 0.0

    def test_valid_coordinates_boundaries(self):
        """Test validation at coordinate boundaries."""
        lon, lat = validate_coordinates(-180, 90)
        assert lon == -180
        assert lat == 90

        lon, lat = validate_coordinates(180, -90)
        assert lon == 180
        assert lat == -90

    def test_invalid_longitude_too_high(self):
        """Test validation with longitude > 180."""
        with pytest.raises(ValueError, match="Longitude must be between"):
            validate_coordinates(181, 40.0)

    def test_invalid_longitude_too_low(self):
        """Test validation with longitude < -180."""
        with pytest.raises(ValueError, match="Longitude must be between"):
            validate_coordinates(-181, 40.0)

    def test_invalid_latitude_too_high(self):
        """Test validation with latitude > 90."""
        with pytest.raises(ValueError, match="Latitude must be between"):
            validate_coordinates(0.0, 91)

    def test_invalid_latitude_too_low(self):
        """Test validation with latitude < -90."""
        with pytest.raises(ValueError, match="Latitude must be between"):
            validate_coordinates(0.0, -91)


class TestGenerateTrackingId:
    """Test generate_tracking_id function."""

    def test_generate_tracking_id_default_prefix(self):
        """Test tracking ID generation with default prefix."""
        tracking_id = generate_tracking_id()
        assert tracking_id.startswith("route-")
        assert len(tracking_id) == len("route-") + 16

    def test_generate_tracking_id_custom_prefix(self):
        """Test tracking ID generation with custom prefix."""
        tracking_id = generate_tracking_id(prefix="test-")
        assert tracking_id.startswith("test-")
        assert len(tracking_id) == len("test-") + 16

    def test_generate_tracking_id_no_prefix(self):
        """Test tracking ID generation with empty prefix."""
        tracking_id = generate_tracking_id(prefix="")
        assert len(tracking_id) == 16

    def test_generate_tracking_id_uniqueness(self):
        """Test that generated tracking IDs are unique."""
        ids = {generate_tracking_id() for _ in range(100)}
        assert len(ids) == 100

    def test_generate_tracking_id_format(self):
        """Test tracking ID format contains only hex characters."""
        tracking_id = generate_tracking_id()
        hex_part = tracking_id.replace("route-", "")
        assert all(c in "0123456789abcdef" for c in hex_part)


class TestValidateTrackingId:
    """Test validate_tracking_id function."""

    def test_valid_tracking_id_with_default_prefix(self):
        """Test validation of valid tracking ID."""
        assert validate_tracking_id("route-abc123") is True

    def test_valid_tracking_id_with_letters(self):
        """Test validation with letters."""
        assert validate_tracking_id("test-ABC123_xyz.end") is True

    def test_valid_tracking_id_with_special_chars(self):
        """Test validation with allowed special characters."""
        assert validate_tracking_id("test-id_123.456-end") is True

    def test_valid_tracking_id_min_length(self):
        """Test validation with minimum length (1 char)."""
        assert validate_tracking_id("a") is True

    def test_valid_tracking_id_max_length(self):
        """Test validation with maximum length (100 chars)."""
        assert validate_tracking_id("a" * 100) is True

    def test_invalid_tracking_id_too_long(self):
        """Test validation with length > 100."""
        assert validate_tracking_id("a" * 101) is False

    def test_invalid_tracking_id_empty(self):
        """Test validation with empty string."""
        assert validate_tracking_id("") is False

    def test_invalid_tracking_id_invalid_chars(self):
        """Test validation with invalid characters."""
        assert validate_tracking_id("test@id") is False
        assert validate_tracking_id("test#id") is False
        assert validate_tracking_id("test id") is False

    def test_generated_tracking_id_is_valid(self):
        """Test that generated tracking IDs pass validation."""
        tracking_id = generate_tracking_id()
        assert validate_tracking_id(tracking_id) is True


class TestBuildAttributesHeader:
    """Test build_attributes_header function."""

    def test_build_attributes_header_no_args(self):
        """Test building header with no arguments."""
        headers = build_attributes_header()
        assert headers == {}

    def test_build_attributes_header_with_attributes(self):
        """Test building header with attributes."""
        headers = build_attributes_header(attributes="routes,summary")
        assert headers == {"Attributes": "routes,summary"}

    def test_build_attributes_header_with_exclude(self):
        """Test building header with exclude attributes."""
        headers = build_attributes_header(attributes_exclude="traffic")
        assert headers == {"Attributes-Exclude": "traffic"}

    def test_build_attributes_header_with_both(self):
        """Test building header with both attributes and exclude."""
        headers = build_attributes_header(
            attributes="routes,summary",
            attributes_exclude="traffic",
        )
        assert headers == {
            "Attributes": "routes,summary",
            "Attributes-Exclude": "traffic",
        }

    def test_build_attributes_header_none_values(self):
        """Test building header with None values."""
        headers = build_attributes_header(attributes=None, attributes_exclude=None)
        assert headers == {}

    def test_build_attributes_header_empty_strings(self):
        """Test building header with empty strings."""
        headers = build_attributes_header(attributes="", attributes_exclude="")
        # Empty strings are falsy, so should not be added
        assert headers == {}


class TestMaskApiKey:
    """Test mask_api_key function."""

    def test_mask_api_key_normal(self):
        """Test masking a normal API key."""
        masked = mask_api_key("dLiYZNKZfCnyTq15Msg7PQAYJDtQEglQ")
        assert masked == "dLiY...EglQ"

    def test_mask_api_key_short(self):
        """Test masking a short API key (8 chars or less)."""
        masked = mask_api_key("short123")
        assert masked == "****"

    def test_mask_api_key_exactly_8_chars(self):
        """Test masking an API key with exactly 8 characters."""
        masked = mask_api_key("12345678")
        assert masked == "****"

    def test_mask_api_key_9_chars(self):
        """Test masking an API key with 9 characters."""
        masked = mask_api_key("123456789")
        assert masked == "1234...6789"

    def test_mask_api_key_very_long(self):
        """Test masking a very long API key."""
        key = "a" * 100 + "b" * 4
        masked = mask_api_key(key)
        assert masked == "aaaa...bbbb"

    def test_mask_api_key_empty(self):
        """Test masking an empty API key."""
        masked = mask_api_key("")
        assert masked == "****"
