"""
Shared GeoJSON schemas.

Provider-agnostic geometry models used by every map layer domain.

All coordinates follow the GeoJSON standard: ``[longitude, latitude]`` in WGS84.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Coordinate = tuple[float, float]

MAX_WAYPOINTS = 150


def validate_lon_lat(longitude: float, latitude: float) -> Coordinate:
    """Validate a single ``[longitude, latitude]`` pair.

    Args:
        longitude: Longitude in range -180..180.
        latitude: Latitude in range -90..90.

    Returns:
        Validated ``(longitude, latitude)`` tuple.

    Raises:
        ValueError: If a coordinate is out of range.
    """
    if not (-180 <= longitude <= 180):
        raise ValueError(f"Longitude must be between -180 and 180, got {longitude}")
    if not (-90 <= latitude <= 90):
        raise ValueError(f"Latitude must be between -90 and 90, got {latitude}")
    return (longitude, latitude)


def _validate_many(coordinates: list[Coordinate]) -> list[Coordinate]:
    """Validate every coordinate pair in a sequence."""
    for lon, lat in coordinates:
        validate_lon_lat(lon, lat)
    return coordinates


class GeoJSONPoint(BaseModel):
    """GeoJSON Point with validated coordinates.

    Coordinates must be [longitude, latitude] in WGS84.
    - longitude: -180 to 180
    - latitude: -90 to 90
    """

    type: Literal["Point"] = "Point"
    coordinates: Coordinate = Field(description="[longitude, latitude] in WGS84")

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, v: Coordinate) -> Coordinate:
        """Validate longitude and latitude ranges."""
        lon, lat = v
        return validate_lon_lat(lon, lat)


class GeoJSONMultiPoint(BaseModel):
    """GeoJSON MultiPoint for waypoints.

    Maximum 150 waypoints supported.
    """

    type: Literal["MultiPoint"] = "MultiPoint"
    coordinates: list[Coordinate] = Field(
        max_length=MAX_WAYPOINTS,
        description="List of [longitude, latitude] coordinates",
    )

    @field_validator("coordinates")
    @classmethod
    def validate_all_coordinates(cls, v: list[Coordinate]) -> list[Coordinate]:
        """Validate all coordinate pairs."""
        return _validate_many(v)


class GeoJSONLineString(BaseModel):
    """GeoJSON LineString for path specification.

    Minimum 2 coordinates required.
    """

    type: Literal["LineString"] = "LineString"
    coordinates: list[Coordinate] = Field(
        min_length=2,
        description="List of [longitude, latitude] coordinates",
    )

    @field_validator("coordinates")
    @classmethod
    def validate_all_coordinates(cls, v: list[Coordinate]) -> list[Coordinate]:
        """Validate all coordinate pairs."""
        return _validate_many(v)


def linestring_to_wkt(coordinates: list[Coordinate], srid: int = 4326) -> str:
    """Build an EWKT ``LINESTRING`` from coordinates.

    Args:
        coordinates: List of ``[longitude, latitude]`` pairs.
        srid: Spatial reference identifier.

    Returns:
        EWKT string, e.g. ``SRID=4326;LINESTRING(1 2, 3 4)``.
    """
    body = ", ".join(f"{lon} {lat}" for lon, lat in coordinates)
    return f"SRID={srid};LINESTRING({body})"


def point_to_wkt(longitude: float, latitude: float, srid: int = 4326) -> str:
    """Build an EWKT ``POINT`` from a coordinate pair.

    Args:
        longitude: Longitude in WGS84.
        latitude: Latitude in WGS84.
        srid: Spatial reference identifier.

    Returns:
        EWKT string, e.g. ``SRID=4326;POINT(1 2)``.
    """
    return f"SRID={srid};POINT({longitude} {latitude})"
