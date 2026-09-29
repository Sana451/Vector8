"""
Shared GeoJSON schemas.

Provider-agnostic geometry models used by every map layer domain.

All coordinates follow the GeoJSON standard: ``[longitude, latitude]`` in WGS84.
"""

import math
from typing import Literal

from flexpolyline import decode, encode  # type: ignore[import-untyped]
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


def encode_flexible_polyline(
    coordinates: list[Coordinate],
    *,
    precision: int = 5,
) -> str:
    """Encode GeoJSON coordinates into a HERE flexible polyline."""

    if precision < 0 or precision > 15:
        raise ValueError("Flexible polyline precision must be between 0 and 15")

    if len(coordinates) < 2:
        raise ValueError("Flexible polyline requires at least 2 coordinates")

    return encode(
        [(lat, lon) for lon, lat in coordinates],
        precision=precision,
    )


def decode_flexible_polyline(encoded: str) -> list[Coordinate]:
    """Decode HERE flexible polyline into (lon, lat)."""

    decoded = decode(encoded)

    return [(lon, lat) for lat, lon in decoded]


def _dedupe_consecutive_coordinates(coordinates: list[Coordinate]) -> list[Coordinate]:
    deduped: list[Coordinate] = []
    for coordinate in coordinates:
        if not deduped or deduped[-1] != coordinate:
            deduped.append(coordinate)
    return deduped


def _project_to_local_meters(
    coordinates: list[Coordinate],
) -> list[tuple[float, float]]:
    average_latitude = math.radians(
        sum(latitude for _, latitude in coordinates) / len(coordinates)
    )
    meters_per_degree_lat = 111_320.0
    meters_per_degree_lon = meters_per_degree_lat * math.cos(average_latitude)

    return [
        (longitude * meters_per_degree_lon, latitude * meters_per_degree_lat)
        for longitude, latitude in coordinates
    ]


def _perpendicular_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    if start == end:
        return math.hypot(point[0] - start[0], point[1] - start[1])

    numerator = abs(
        (end[0] - start[0]) * (start[1] - point[1])
        - (start[0] - point[0]) * (end[1] - start[1])
    )
    denominator = math.hypot(end[0] - start[0], end[1] - start[1])
    return numerator / denominator


def simplify_coordinates_rdp(
    coordinates: list[Coordinate],
    *,
    tolerance_meters: float,
) -> list[Coordinate]:
    """Simplify a route with Ramer-Douglas-Peucker while preserving endpoints."""
    if len(coordinates) <= 2:
        return coordinates

    projected = _project_to_local_meters(coordinates)

    def _simplify(start_index: int, end_index: int) -> list[int]:
        max_distance = -1.0
        split_index = -1

        for candidate_index in range(start_index + 1, end_index):
            distance = _perpendicular_distance(
                projected[candidate_index],
                projected[start_index],
                projected[end_index],
            )
            if distance > max_distance:
                max_distance = distance
                split_index = candidate_index

        if max_distance <= tolerance_meters or split_index == -1:
            return [start_index, end_index]

        left = _simplify(start_index, split_index)
        right = _simplify(split_index, end_index)
        return left[:-1] + right

    indexes = sorted(set(_simplify(0, len(coordinates) - 1)))
    return [coordinates[index] for index in indexes]


def simplify_route_for_here(
    coordinates: list[Coordinate],
    *,
    target_points: int = 300,
    max_encoded_length: int = 1800,
    initial_tolerance_meters: float = 25.0,
    precision: int = 5,
) -> list[Coordinate]:
    """Simplify a route until it is suitable for HERE route search."""
    deduped = _dedupe_consecutive_coordinates(coordinates)
    if len(deduped) < 2:
        raise ValueError("A HERE search route requires at least 2 coordinates")

    candidate = deduped
    if (
        len(candidate) <= target_points
        and len(encode_flexible_polyline(candidate, precision=precision))
        <= max_encoded_length
    ):
        return candidate

    tolerance = initial_tolerance_meters
    for _ in range(16):
        simplified = simplify_coordinates_rdp(
            deduped,
            tolerance_meters=tolerance,
        )
        candidate = simplified if len(simplified) >= 2 else [deduped[0], deduped[-1]]
        encoded_length = len(encode_flexible_polyline(candidate, precision=precision))
        if len(candidate) <= target_points and encoded_length <= max_encoded_length:
            return candidate
        tolerance *= 2

    return candidate
