"""
Routing utilities.

Pure utility functions for coordinate validation, tracking ID generation, etc.
"""

import re
import uuid


def validate_coordinates(longitude: float, latitude: float) -> tuple[float, float]:
    """Validate coordinate pair.

    Args:
        longitude: -180 to 180
        latitude: -90 to 90

    Returns:
        Validated (longitude, latitude) tuple

    Raises:
        ValueError: If coordinates are out of range
    """
    if not (-180 <= longitude <= 180):
        raise ValueError(f"Longitude must be between -180 and 180, got {longitude}")
    if not (-90 <= latitude <= 90):
        raise ValueError(f"Latitude must be between -90 and 90, got {latitude}")
    return (longitude, latitude)


def generate_tracking_id(prefix: str = "route-") -> str:
    """Generate a tracking ID for request correlation.

    Args:
        prefix: Optional prefix for the tracking ID

    Returns:
        Tracking ID in format: {prefix}{uuid}
    """
    return f"{prefix}{uuid.uuid4().hex[:16]}"


def validate_tracking_id(tracking_id: str) -> bool:
    """Validate tracking ID format.

    Tracking ID must match: ^[a-zA-Z0-9-_.]{1,100}$

    Args:
        tracking_id: Tracking ID to validate

    Returns:
        True if valid, False otherwise
    """
    pattern = r"^[a-zA-Z0-9\-_.]{1,100}$"
    return bool(re.match(pattern, tracking_id))


def build_attributes_header(
    attributes: str | None = None,
    attributes_exclude: str | None = None,
) -> dict[str, str]:
    """Build TomTom attributes headers.

    Args:
        attributes: Attributes to include in response
        attributes_exclude: Attributes to exclude from response

    Returns:
        Dictionary with Attributes headers for HTTP request
    """
    headers = {}
    if attributes:
        headers["Attributes"] = attributes
    if attributes_exclude:
        headers["Attributes-Exclude"] = attributes_exclude
    return headers


def mask_api_key(api_key: str) -> str:
    """Mask API key for logging.

    Args:
        api_key: API key to mask

    Returns:
        Masked API key (first 4 and last 4 chars visible)
    """
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}...{api_key[-4:]}"
