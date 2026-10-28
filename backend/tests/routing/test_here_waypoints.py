"""Tests for HERE waypoint handling: via parameters, stop duration, splitting."""

from __future__ import annotations

import pytest

from app.providers.geo import GeoJSONMultiPoint, GeoJSONPoint
from app.providers.here.constants import MAX_VIA_POINTS_PER_REQUEST
from app.providers.here.routing import HereRoutingProvider
from app.routing.schemas import CalculateRouteRequest, RoutePlanningLocations

ORIGIN = (-74.006, 40.7128)
DESTINATION = (-73.9855, 40.758)


def build_request(
    waypoints: list[tuple[float, float]] | None = None,
    *,
    stop_duration_seconds: int | None = None,
) -> CalculateRouteRequest:
    return CalculateRouteRequest(
        route_planning_locations=RoutePlanningLocations(
            origin=GeoJSONPoint(coordinates=ORIGIN),
            destination=GeoJSONPoint(coordinates=DESTINATION),
            waypoints=(
                GeoJSONMultiPoint(coordinates=waypoints)
                if waypoints is not None
                else None
            ),
            waypoint_stop_duration_seconds=stop_duration_seconds,
        ),
    )


def make_waypoints(count: int) -> list[tuple[float, float]]:
    return [(-74.0 + index / 100, 40.0 + index / 100) for index in range(count)]


class TestViaParameters:
    def test_no_via_parameter_without_waypoints(self) -> None:
        params = HereRoutingProvider()._build_params(build_request(), api_key="k")

        assert "via" not in params

    def test_via_is_a_list_of_lat_lon_pairs(self) -> None:
        params = HereRoutingProvider()._build_params(
            build_request([(-75.0, 41.0), (-76.0, 42.0)]),
            api_key="k",
        )

        assert params["via"] == ["41.0,-75.0", "42.0,-76.0"]

    def test_via_order_is_preserved(self) -> None:
        waypoints = make_waypoints(5)

        params = HereRoutingProvider()._build_params(
            build_request(waypoints),
            api_key="k",
        )

        assert params["via"] == [f"{lat},{lon}" for lon, lat in waypoints]

    def test_stop_duration_marks_waypoints_as_real_stops(self) -> None:
        params = HereRoutingProvider()._build_params(
            build_request([(-75.0, 41.0)], stop_duration_seconds=900),
            api_key="k",
        )

        assert params["via"] == ["41.0,-75.0!stopDuration=900"]

    def test_zero_stop_duration_is_sent_explicitly(self) -> None:
        params = HereRoutingProvider()._build_params(
            build_request([(-75.0, 41.0)], stop_duration_seconds=0),
            api_key="k",
        )

        assert params["via"] == ["41.0,-75.0!stopDuration=0"]


class TestSegmentSplitting:
    def test_single_segment_when_within_limit(self) -> None:
        waypoints = make_waypoints(MAX_VIA_POINTS_PER_REQUEST)

        segments = HereRoutingProvider._split_into_segments(build_request(waypoints))

        assert len(segments) == 1
        origin, via, destination = segments[0]
        assert origin == ORIGIN
        assert destination == DESTINATION
        assert len(via) == MAX_VIA_POINTS_PER_REQUEST

    def test_splits_when_over_limit(self) -> None:
        waypoints = make_waypoints(MAX_VIA_POINTS_PER_REQUEST + 5)

        segments = HereRoutingProvider._split_into_segments(build_request(waypoints))

        assert len(segments) == 2

    def test_split_keeps_endpoints(self) -> None:
        waypoints = make_waypoints(MAX_VIA_POINTS_PER_REQUEST * 2 + 3)

        segments = HereRoutingProvider._split_into_segments(build_request(waypoints))

        assert segments[0][0] == ORIGIN
        assert segments[-1][2] == DESTINATION

    def test_segments_are_chained(self) -> None:
        waypoints = make_waypoints(MAX_VIA_POINTS_PER_REQUEST * 2 + 3)

        segments = HereRoutingProvider._split_into_segments(build_request(waypoints))

        for previous, current in zip(segments, segments[1:], strict=False):
            assert previous[2] == current[0]

    def test_every_waypoint_is_visited_exactly_once(self) -> None:
        waypoints = make_waypoints(MAX_VIA_POINTS_PER_REQUEST * 2 + 7)

        segments = HereRoutingProvider._split_into_segments(build_request(waypoints))

        visited: list[tuple[float, float]] = []
        for index, (_, via, destination) in enumerate(segments):
            visited.extend(via)
            if index < len(segments) - 1:
                # Boundary waypoints are visited as a segment destination.
                visited.append(destination)

        assert visited == waypoints

    def test_no_segment_exceeds_the_limit(self) -> None:
        waypoints = make_waypoints(MAX_VIA_POINTS_PER_REQUEST * 2 + 7)

        segments = HereRoutingProvider._split_into_segments(build_request(waypoints))

        assert all(len(via) <= MAX_VIA_POINTS_PER_REQUEST for _, via, _ in segments)

    def test_single_segment_without_waypoints(self) -> None:
        segments = HereRoutingProvider._split_into_segments(build_request())

        assert segments == [(ORIGIN, [], DESTINATION)]


def here_payload(*sections: tuple[int, int]) -> dict:
    # "BFoz5xJ67i1B1B7PzIhaxL7Y" is a valid flexible polyline.
    return {
        "routes": [
            {
                "sections": [
                    {
                        "summary": {"length": length, "duration": duration},
                        "polyline": "BFoz5xJ67i1B1B7PzIhaxL7Y",
                    }
                    for length, duration in sections
                ]
            }
        ]
    }


class TestResponseMerging:
    def test_legs_from_all_segments_are_concatenated(self) -> None:
        response = HereRoutingProvider()._transform_response(
            [here_payload((100, 10), (200, 20)), here_payload((300, 30))]
        )

        assert len(response.routes) == 1
        assert len(response.routes[0].legs) == 3

    def test_totals_are_summed_across_segments(self) -> None:
        response = HereRoutingProvider()._transform_response(
            [here_payload((100, 10), (200, 20)), here_payload((300, 30))]
        )

        summary = response.routes[0].summary
        assert summary.length_in_meters == 600
        assert summary.travel_duration_in_seconds == 60

    def test_leg_summaries_are_per_section(self) -> None:
        response = HereRoutingProvider()._transform_response(
            [here_payload((100, 10), (200, 20))]
        )

        lengths = [leg.summary.length_in_meters for leg in response.routes[0].legs]
        assert lengths == [100, 200]

    def test_legs_carry_decoded_geometry(self) -> None:
        response = HereRoutingProvider()._transform_response([here_payload((100, 10))])

        path = response.routes[0].legs[0].path
        assert path is not None
        assert len(path.coordinates) > 0

    def test_empty_routes_raise(self) -> None:
        from app.routing.exceptions import RoutingProviderError

        with pytest.raises(RoutingProviderError):
            HereRoutingProvider()._transform_response([{"routes": []}])
