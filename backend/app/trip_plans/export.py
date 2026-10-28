"""Export a trip plan to formats a driver's navigator can open.

The refined route geometry can hold tens of thousands of vertices, which many
consumer navigators refuse to load, so the track is thinned to
``MAX_TRACK_POINTS`` while the fuel stops are always exported in full: losing a
track vertex costs nothing, losing a stop costs the driver a refuel.
"""

from __future__ import annotations

import csv
import io
from decimal import Decimal
from xml.etree import ElementTree as ET

from app.trip_plans.schemas import TripPlanStopSnapshot

MAX_TRACK_POINTS = 2000

GPX_NAMESPACE = "http://www.topografix.com/GPX/1/1"
KML_NAMESPACE = "http://www.opengis.net/kml/2.2"

CSV_COLUMNS = [
    "sequence",
    "kind",
    "label",
    "longitude",
    "latitude",
    "route_offset_meters",
    "fuel_added_gallons",
    "fuel_price_per_gallon",
    "fuel_cost",
    "detour_distance_meters",
    "detour_time_seconds",
]


def thin_track(
    coordinates: list[tuple[float, float]], max_points: int = MAX_TRACK_POINTS
) -> list[tuple[float, float]]:
    """Reduce a track to at most ``max_points`` vertices.

    Uniform striding is used rather than a shape-preserving simplification:
    the geometry comes back from the provider already densified along the road,
    so every n-th vertex still traces the same roads.
    """
    if max_points < 2:
        raise ValueError("max_points must be at least 2")
    if len(coordinates) <= max_points:
        return list(coordinates)

    stride = (len(coordinates) - 1) / (max_points - 1)
    thinned = [coordinates[round(index * stride)] for index in range(max_points - 1)]
    thinned.append(coordinates[-1])
    return thinned


def _decimal_text(value: Decimal | int | float | None) -> str:
    return "" if value is None else str(value)


def build_gpx(
    *,
    name: str,
    stops: list[TripPlanStopSnapshot],
    coordinates: list[tuple[float, float]],
) -> str:
    """Build a GPX 1.1 document with stop waypoints and a route track."""
    ET.register_namespace("", GPX_NAMESPACE)
    gpx = ET.Element(
        f"{{{GPX_NAMESPACE}}}gpx",
        {"version": "1.1", "creator": "Vector8"},
    )

    metadata = ET.SubElement(gpx, f"{{{GPX_NAMESPACE}}}metadata")
    ET.SubElement(metadata, f"{{{GPX_NAMESPACE}}}name").text = name

    for stop in stops:
        longitude, latitude = stop.coordinate
        waypoint = ET.SubElement(
            gpx,
            f"{{{GPX_NAMESPACE}}}wpt",
            {"lat": str(latitude), "lon": str(longitude)},
        )
        ET.SubElement(waypoint, f"{{{GPX_NAMESPACE}}}name").text = stop.label
        ET.SubElement(waypoint, f"{{{GPX_NAMESPACE}}}type").text = stop.kind
        description = _stop_description(stop)
        if description:
            ET.SubElement(waypoint, f"{{{GPX_NAMESPACE}}}desc").text = description

    if coordinates:
        track = ET.SubElement(gpx, f"{{{GPX_NAMESPACE}}}trk")
        ET.SubElement(track, f"{{{GPX_NAMESPACE}}}name").text = name
        segment = ET.SubElement(track, f"{{{GPX_NAMESPACE}}}trkseg")
        for longitude, latitude in thin_track(coordinates):
            ET.SubElement(
                segment,
                f"{{{GPX_NAMESPACE}}}trkpt",
                {"lat": str(latitude), "lon": str(longitude)},
            )

    return _serialize(gpx)


def build_kml(
    *,
    name: str,
    stops: list[TripPlanStopSnapshot],
    coordinates: list[tuple[float, float]],
) -> str:
    """Build a KML document with stop placemarks and a route line."""
    ET.register_namespace("", KML_NAMESPACE)
    kml = ET.Element(f"{{{KML_NAMESPACE}}}kml")
    document = ET.SubElement(kml, f"{{{KML_NAMESPACE}}}Document")
    ET.SubElement(document, f"{{{KML_NAMESPACE}}}name").text = name

    if coordinates:
        placemark = ET.SubElement(document, f"{{{KML_NAMESPACE}}}Placemark")
        ET.SubElement(placemark, f"{{{KML_NAMESPACE}}}name").text = f"{name} route"
        line = ET.SubElement(placemark, f"{{{KML_NAMESPACE}}}LineString")
        ET.SubElement(line, f"{{{KML_NAMESPACE}}}tessellate").text = "1"
        ET.SubElement(line, f"{{{KML_NAMESPACE}}}coordinates").text = " ".join(
            f"{longitude},{latitude},0"
            for longitude, latitude in thin_track(coordinates)
        )

    for stop in stops:
        longitude, latitude = stop.coordinate
        placemark = ET.SubElement(document, f"{{{KML_NAMESPACE}}}Placemark")
        ET.SubElement(placemark, f"{{{KML_NAMESPACE}}}name").text = stop.label
        description = _stop_description(stop)
        if description:
            ET.SubElement(
                placemark, f"{{{KML_NAMESPACE}}}description"
            ).text = description
        point = ET.SubElement(placemark, f"{{{KML_NAMESPACE}}}Point")
        ET.SubElement(
            point, f"{{{KML_NAMESPACE}}}coordinates"
        ).text = f"{longitude},{latitude},0"

    return _serialize(kml)


def build_csv(stops: list[TripPlanStopSnapshot]) -> str:
    """Build a stop list for accounting, one row per stop."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)

    for stop in stops:
        longitude, latitude = stop.coordinate
        writer.writerow(
            [
                stop.sequence,
                stop.kind,
                stop.label,
                longitude,
                latitude,
                _decimal_text(stop.route_offset_meters),
                _decimal_text(stop.fuel_added_gallons),
                _decimal_text(stop.fuel_price_per_gallon),
                _decimal_text(stop.fuel_cost),
                _decimal_text(stop.detour_distance_meters),
                _decimal_text(stop.detour_time_seconds),
            ]
        )

    return buffer.getvalue()


def _stop_description(stop: TripPlanStopSnapshot) -> str:
    parts: list[str] = []
    if stop.fuel_added_gallons is not None:
        parts.append(f"Fuel: {stop.fuel_added_gallons} gal")
    if stop.fuel_price_per_gallon is not None:
        parts.append(f"Price: ${stop.fuel_price_per_gallon}/gal")
    if stop.fuel_cost is not None:
        parts.append(f"Cost: ${stop.fuel_cost}")
    return "; ".join(parts)


def _serialize(root: ET.Element) -> str:
    return ET.tostring(root, encoding="unicode", xml_declaration=True)
