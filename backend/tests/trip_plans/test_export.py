"""GPX, KML and CSV generation for trip plans."""

import csv
import io
from decimal import Decimal
from xml.etree import ElementTree as ET

import pytest

from app.trip_plans.export import (
    GPX_NAMESPACE,
    KML_NAMESPACE,
    build_csv,
    build_gpx,
    build_kml,
    thin_track,
)
from app.trip_plans.schemas import TripPlanStopSnapshot

COORDINATES = [(-97.5, 33.2), (-97.6, 33.4), (-97.7, 33.6)]


def make_stop(sequence: int = 1, label: str = "Love's #200") -> TripPlanStopSnapshot:
    return TripPlanStopSnapshot(
        sequence=sequence,
        kind="refuel",
        label=label,
        coordinate=(-97.5687, 33.2025),
        fuel_added_gallons=Decimal("21.05"),
        fuel_price_per_gallon=Decimal("5.76"),
        fuel_cost=Decimal("121.28"),
        detour_distance_meters=Decimal("3218.7"),
        detour_time_seconds=120,
    )


class TestThinTrack:
    def test_short_track_is_returned_unchanged(self) -> None:
        assert thin_track(COORDINATES, max_points=10) == COORDINATES

    def test_track_is_capped_at_max_points(self) -> None:
        track = [(float(index), 0.0) for index in range(5000)]

        thinned = thin_track(track, max_points=100)

        assert len(thinned) == 100

    def test_endpoints_are_preserved(self) -> None:
        track = [(float(index), 0.0) for index in range(5000)]

        thinned = thin_track(track, max_points=50)

        assert thinned[0] == track[0]
        assert thinned[-1] == track[-1]

    def test_order_is_preserved(self) -> None:
        track = [(float(index), 0.0) for index in range(1000)]

        thinned = thin_track(track, max_points=25)

        assert thinned == sorted(thinned)

    def test_max_points_below_two_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            thin_track(COORDINATES, max_points=1)


class TestBuildGpx:
    def test_waypoints_and_track_are_written(self) -> None:
        document = build_gpx(
            name="Dallas run", stops=[make_stop()], coordinates=COORDINATES
        )
        root = ET.fromstring(document)

        waypoints = root.findall(f"{{{GPX_NAMESPACE}}}wpt")
        points = root.findall(
            f"{{{GPX_NAMESPACE}}}trk/{{{GPX_NAMESPACE}}}trkseg/{{{GPX_NAMESPACE}}}trkpt"
        )

        assert len(waypoints) == 1
        assert len(points) == len(COORDINATES)

    def test_waypoint_uses_latitude_longitude_order(self) -> None:
        root = ET.fromstring(
            build_gpx(name="Trip", stops=[make_stop()], coordinates=[])
        )

        waypoint = root.find(f"{{{GPX_NAMESPACE}}}wpt")

        assert waypoint is not None
        assert waypoint.get("lat") == "33.2025"
        assert waypoint.get("lon") == "-97.5687"

    def test_fuel_details_land_in_the_description(self) -> None:
        root = ET.fromstring(
            build_gpx(name="Trip", stops=[make_stop()], coordinates=[])
        )

        description = root.find(f"{{{GPX_NAMESPACE}}}wpt/{{{GPX_NAMESPACE}}}desc")

        assert description is not None
        assert description.text is not None
        assert "21.05 gal" in description.text
        assert "$5.76/gal" in description.text

    def test_missing_geometry_omits_the_track(self) -> None:
        root = ET.fromstring(
            build_gpx(name="Trip", stops=[make_stop()], coordinates=[])
        )

        assert root.find(f"{{{GPX_NAMESPACE}}}trk") is None

    def test_long_geometry_is_thinned(self) -> None:
        track = [(float(index) / 1000, 33.0) for index in range(9000)]

        root = ET.fromstring(build_gpx(name="Trip", stops=[], coordinates=track))
        points = root.findall(
            f"{{{GPX_NAMESPACE}}}trk/{{{GPX_NAMESPACE}}}trkseg/{{{GPX_NAMESPACE}}}trkpt"
        )

        assert len(points) == 2000


class TestBuildKml:
    def test_line_and_placemarks_are_written(self) -> None:
        root = ET.fromstring(
            build_kml(
                name="Dallas run",
                stops=[make_stop(), make_stop(sequence=2, label="Petro #7")],
                coordinates=COORDINATES,
            )
        )

        placemarks = root.findall(
            f"{{{KML_NAMESPACE}}}Document/{{{KML_NAMESPACE}}}Placemark"
        )

        # One placemark for the route line plus one per stop.
        assert len(placemarks) == 3

    def test_coordinates_use_longitude_latitude_order(self) -> None:
        root = ET.fromstring(build_kml(name="Trip", stops=[], coordinates=COORDINATES))

        line = root.find(
            f"{{{KML_NAMESPACE}}}Document/{{{KML_NAMESPACE}}}Placemark/"
            f"{{{KML_NAMESPACE}}}LineString/{{{KML_NAMESPACE}}}coordinates"
        )

        assert line is not None
        assert line.text is not None
        assert line.text.split(" ")[0] == "-97.5,33.2,0"

    def test_missing_geometry_omits_the_line(self) -> None:
        root = ET.fromstring(
            build_kml(name="Trip", stops=[make_stop()], coordinates=[])
        )

        assert (
            root.find(
                f"{{{KML_NAMESPACE}}}Document/{{{KML_NAMESPACE}}}Placemark/"
                f"{{{KML_NAMESPACE}}}LineString"
            )
            is None
        )


class TestBuildCsv:
    def test_header_and_row_are_written(self) -> None:
        content = build_csv([make_stop()])

        rows = list(csv.reader(io.StringIO(content)))

        assert rows[0][:3] == ["sequence", "kind", "label"]
        assert rows[1][:3] == ["1", "refuel", "Love's #200"]

    def test_empty_values_stay_empty(self) -> None:
        stop = TripPlanStopSnapshot(
            sequence=1, kind="start", label="Origin", coordinate=(-97.0, 33.0)
        )

        rows = list(csv.reader(io.StringIO(build_csv([stop]))))

        assert rows[1][6] == ""

    def test_every_stop_is_exported(self) -> None:
        stops = [make_stop(sequence=index) for index in range(1, 8)]

        rows = list(csv.reader(io.StringIO(build_csv(stops))))

        assert len(rows) == len(stops) + 1
