"""Tests for HERE route geometry helpers."""

from app.providers.geo import (
    decode_flexible_polyline,
    encode_flexible_polyline,
    simplify_route_for_here,
)


def test_flexible_polyline_round_trip_preserves_coordinates():
    coordinates = [
        (-87.74529, 41.88978),
        (-87.70001, 41.91002),
        (-87.65055, 41.95012),
    ]

    encoded = encode_flexible_polyline(coordinates)
    decoded = decode_flexible_polyline(encoded)

    assert len(decoded) == len(coordinates)
    for (expected_lon, expected_lat), (actual_lon, actual_lat) in zip(
        coordinates, decoded, strict=True
    ):
        assert actual_lon == expected_lon
        assert actual_lat == expected_lat


def test_simplify_route_for_here_preserves_endpoints_and_reduces_points():
    coordinates = [
        (-87.9 + index * 0.001, 41.8 + ((index % 12) * 0.0008)) for index in range(1000)
    ]

    simplified = simplify_route_for_here(coordinates, target_points=120)

    assert simplified[0] == coordinates[0]
    assert simplified[-1] == coordinates[-1]
    assert len(simplified) <= 120
    assert len(simplified) < len(coordinates)


def test_simplify_route_for_here_handles_duplicate_consecutive_points():
    coordinates = [
        (-87.0, 41.0),
        (-87.0, 41.0),
        (-86.9, 41.1),
        (-86.9, 41.1),
        (-86.8, 41.2),
    ]

    simplified = simplify_route_for_here(coordinates, target_points=10)

    assert simplified == [(-87.0, 41.0), (-86.9, 41.1), (-86.8, 41.2)]
