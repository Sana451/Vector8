"""Domain enums for trip plans."""

from __future__ import annotations

from enum import StrEnum


class TripPlanStatus(StrEnum):
    """Lifecycle of a trip plan."""

    DRAFT = "draft"
    REFINED = "refined"
    REFINE_FAILED = "refine_failed"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TripPlanExportFormat(StrEnum):
    """Download formats offered for a trip plan."""

    GPX = "gpx"
    KML = "kml"
    CSV = "csv"


EXPORT_MEDIA_TYPES: dict[TripPlanExportFormat, str] = {
    TripPlanExportFormat.GPX: "application/gpx+xml",
    TripPlanExportFormat.KML: "application/vnd.google-earth.kml+xml",
    TripPlanExportFormat.CSV: "text/csv",
}
