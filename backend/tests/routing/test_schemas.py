"""
Tests for routing schemas.

Tests coordinate validation, enums, and constraint handling.
"""

import pytest
from pydantic import ValidationError

from app.routing.schemas import (
    AvoidAreaRectangle,
    AvoidType,
    CalculateRouteRequest,
    EngineType,
    GeoJSONLineString,
    GeoJSONMultiPoint,
    GeoJSONPoint,
    RoutePlanningLocations,
    RouteStop,
    TrafficMode,
)


class TestGeoJSONPoint:
    """Test GeoJSON Point validation."""

    def test_valid_point(self):
        """Test valid point creation."""
        point = GeoJSONPoint(coordinates=[-74.006, 40.7128])
        assert point.coordinates == (-74.006, 40.7128)
        assert point.type == "Point"

    def test_invalid_longitude_high(self):
        """Test invalid longitude > 180."""
        with pytest.raises(ValidationError) as exc_info:
            GeoJSONPoint(coordinates=[181, 40])
        assert "Longitude must be between -180 and 180" in str(exc_info.value)

    def test_invalid_longitude_low(self):
        """Test invalid longitude < -180."""
        with pytest.raises(ValidationError) as exc_info:
            GeoJSONPoint(coordinates=[-181, 40])
        assert "Longitude must be between -180 and 180" in str(exc_info.value)

    def test_invalid_latitude_high(self):
        """Test invalid latitude > 90."""
        with pytest.raises(ValidationError) as exc_info:
            GeoJSONPoint(coordinates=[0, 91])
        assert "Latitude must be between -90 and 90" in str(exc_info.value)

    def test_invalid_latitude_low(self):
        """Test invalid latitude < -90."""
        with pytest.raises(ValidationError) as exc_info:
            GeoJSONPoint(coordinates=[0, -91])
        assert "Latitude must be between -90 and 90" in str(exc_info.value)

    def test_boundary_coordinates(self):
        """Test boundary coordinates are valid."""
        point = GeoJSONPoint(coordinates=[180, 90])
        assert point.coordinates == (180, 90)

        point = GeoJSONPoint(coordinates=[-180, -90])
        assert point.coordinates == (-180, -90)


class TestGeoJSONMultiPoint:
    """Test GeoJSON MultiPoint validation."""

    def test_valid_multipoint(self):
        """Test valid multipoint creation."""
        mp = GeoJSONMultiPoint(
            coordinates=[
                [-74.006, 40.7128],
                [-73.935, 40.7306],
            ]
        )
        assert len(mp.coordinates) == 2
        assert mp.type == "MultiPoint"

    def test_too_many_waypoints(self):
        """Test that more than 150 waypoints are rejected."""
        coords = [[0, 0] for _ in range(151)]
        with pytest.raises(ValidationError) as exc_info:
            GeoJSONMultiPoint(coordinates=coords)
        assert (
            "too_long" in str(exc_info.value).lower()
            or "should have at most" in str(exc_info.value).lower()
        )

    def test_invalid_coordinate_in_multipoint(self):
        """Test invalid coordinate in multipoint."""
        with pytest.raises(ValidationError) as exc_info:
            GeoJSONMultiPoint(coordinates=[[0, 0], [200, 40]])
        assert "Longitude must be between -180 and 180" in str(exc_info.value)


class TestGeoJSONLineString:
    """Test GeoJSON LineString validation."""

    def test_valid_linestring(self):
        """Test valid linestring creation."""
        ls = GeoJSONLineString(
            coordinates=[
                [-74.006, 40.7128],
                [-73.935, 40.7306],
            ]
        )
        assert len(ls.coordinates) == 2
        assert ls.type == "LineString"

    def test_linestring_minimum_coords(self):
        """Test linestring with exactly 2 coordinates."""
        ls = GeoJSONLineString(
            coordinates=[
                [0, 0],
                [1, 1],
            ]
        )
        assert len(ls.coordinates) == 2

    def test_linestring_single_coordinate(self):
        """Test linestring with less than 2 coordinates fails."""
        with pytest.raises(ValidationError) as exc_info:
            GeoJSONLineString(coordinates=[[0, 0]])
        assert "at least 2 items" in str(exc_info.value).lower()


class TestAvoidAreaRectangle:
    """Test avoid area rectangle validation."""

    def test_valid_rectangle(self):
        """Test valid rectangle creation."""
        rect = AvoidAreaRectangle(bbox=[-74.1, 40.6, -73.9, 40.8])
        assert rect.type == "Feature"
        assert rect.geometry is None
        assert rect.bbox == (-74.1, 40.6, -73.9, 40.8)

    def test_invalid_bbox_reversed_lon(self):
        """Test that reversed longitude bbox is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AvoidAreaRectangle(bbox=[-73.9, 40.6, -74.1, 40.8])
        assert "Southwest longitude must be <= northeast longitude" in str(
            exc_info.value
        )

    def test_invalid_bbox_reversed_lat(self):
        """Test that reversed latitude bbox is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AvoidAreaRectangle(bbox=[-74.1, 40.8, -73.9, 40.6])
        assert "Southwest latitude must be <= northeast latitude" in str(exc_info.value)

    def test_invalid_bbox_coordinates(self):
        """Test invalid bbox coordinates."""
        with pytest.raises(ValidationError) as exc_info:
            AvoidAreaRectangle(bbox=[200, 40, 180, 50])
        error_str = str(exc_info.value).lower()
        assert "longitude" in error_str or "between -180 and 180" in error_str


class TestRouteStop:
    """Test route stop validation."""

    def test_valid_route_stop(self):
        """Test valid route stop creation."""
        stop = RouteStop(pause_duration_in_seconds=60)
        assert stop.pause_duration_in_seconds == 60

    def test_negative_pause_duration(self):
        """Test that negative pause duration is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RouteStop(pause_duration_in_seconds=-1)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_entry_point_index_out_of_range(self):
        """Test that preferred_entry_point_index out of range is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RouteStop(
                entry_points=[
                    GeoJSONPoint(coordinates=[0, 0]),
                    GeoJSONPoint(coordinates=[1, 1]),
                ],
                preferred_entry_point_index=5,
            )
        assert "must be 0 <=" in str(exc_info.value)


class TestCalculateRouteRequest:
    """Test calculate route request validation."""

    def test_valid_basic_request(self):
        """Test valid basic route request."""
        request = CalculateRouteRequest(
            route_planning_locations=RoutePlanningLocations(
                origin=GeoJSONPoint(coordinates=[-74.006, 40.7128]),
                destination=GeoJSONPoint(coordinates=[-73.935, 40.7306]),
            )
        )
        assert request.route_planning_locations is not None

    def test_request_with_waypoints(self):
        """Test request with waypoints."""
        request = CalculateRouteRequest(
            route_planning_locations=RoutePlanningLocations(
                origin=GeoJSONPoint(coordinates=[-74.006, 40.7128]),
                destination=GeoJSONPoint(coordinates=[-73.935, 40.7306]),
                waypoints=GeoJSONMultiPoint(
                    coordinates=[
                        [-74.00, 40.72],
                        [-73.95, 40.73],
                    ]
                ),
            ),
            route_type="fast",
            traffic="live",
        )
        assert request.route_planning_locations.waypoints is not None

    def test_invalid_max_alternative_routes(self):
        """Test that max_path_alternative_routes > 5 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CalculateRouteRequest(
                route_planning_locations=RoutePlanningLocations(
                    origin=GeoJSONPoint(coordinates=[0, 0]),
                    destination=GeoJSONPoint(coordinates=[1, 1]),
                ),
                max_path_alternative_routes=10,
            )
        assert "less than or equal to 5" in str(exc_info.value)

    def test_invalid_vehicle_heading(self):
        """Test that invalid vehicle heading is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CalculateRouteRequest(
                route_planning_locations=RoutePlanningLocations(
                    origin=GeoJSONPoint(coordinates=[0, 0]),
                    destination=GeoJSONPoint(coordinates=[1, 1]),
                ),
                vehicle_heading_in_degrees=360,
            )
        assert "less than or equal to 359" in str(exc_info.value)

    def test_invalid_vehicle_speed(self):
        """Test that invalid vehicle speed is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CalculateRouteRequest(
                route_planning_locations=RoutePlanningLocations(
                    origin=GeoJSONPoint(coordinates=[0, 0]),
                    destination=GeoJSONPoint(coordinates=[1, 1]),
                ),
                vehicle_max_speed_in_kilometers_per_hour=300,
            )
        assert "less than or equal to 250" in str(exc_info.value)

    def test_invalid_vehicle_weight(self):
        """Test that negative vehicle weight is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CalculateRouteRequest(
                route_planning_locations=RoutePlanningLocations(
                    origin=GeoJSONPoint(coordinates=[0, 0]),
                    destination=GeoJSONPoint(coordinates=[1, 1]),
                ),
                vehicle_weight_in_kilograms=-100,
            )
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_empty_avoids_list_invalid(self):
        """Test that empty avoids list is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CalculateRouteRequest(
                route_planning_locations=RoutePlanningLocations(
                    origin=GeoJSONPoint(coordinates=[0, 0]),
                    destination=GeoJSONPoint(coordinates=[1, 1]),
                ),
                avoids=[],
            )
        error_str = str(exc_info.value).lower()
        assert "too_short" in error_str or "at least 1" in error_str

    def test_valid_avoid_types(self):
        """Test valid avoid types."""
        request = CalculateRouteRequest(
            route_planning_locations=RoutePlanningLocations(
                origin=GeoJSONPoint(coordinates=[0, 0]),
                destination=GeoJSONPoint(coordinates=[1, 1]),
            ),
            avoids=[AvoidType.TOLL_ROADS, AvoidType.MOTORWAYS],
        )
        assert len(request.avoids) == 2

    def test_invalid_tracking_id_format(self):
        """Test that invalid tracking ID format is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CalculateRouteRequest(
                route_planning_locations=RoutePlanningLocations(
                    origin=GeoJSONPoint(coordinates=[0, 0]),
                    destination=GeoJSONPoint(coordinates=[1, 1]),
                ),
                tracking_id="invalid@tracking#id",
            )
        assert "string should match pattern" in str(exc_info.value).lower()

    def test_valid_engine_types(self):
        """Test valid engine types."""
        request = CalculateRouteRequest(
            route_planning_locations=RoutePlanningLocations(
                origin=GeoJSONPoint(coordinates=[0, 0]),
                destination=GeoJSONPoint(coordinates=[1, 1]),
            ),
            vehicle_engine_type=EngineType.COMBUSTION,
        )
        assert request.vehicle_engine_type == EngineType.COMBUSTION

    def test_valid_traffic_modes(self):
        """Test valid traffic modes."""
        request = CalculateRouteRequest(
            route_planning_locations=RoutePlanningLocations(
                origin=GeoJSONPoint(coordinates=[0, 0]),
                destination=GeoJSONPoint(coordinates=[1, 1]),
            ),
            traffic=TrafficMode.LIVE,
        )
        assert request.traffic == TrafficMode.LIVE
