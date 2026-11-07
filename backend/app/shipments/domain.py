"""Domain enums for shipments.

A shipment is one freight order taken from a broker's rate confirmation. The
document intake flow and the trip planning flow are deliberately decoupled:
intake ends with a reviewed shipment, planning happens later and may never
happen at all.
"""

from __future__ import annotations

from enum import StrEnum


class StopKind(StrEnum):
    """What happens at a shipment stop."""

    PICKUP = "pickup"
    DROPOFF = "dropoff"


class PlanningStatus(StrEnum):
    """Whether a trip has been planned for the shipment yet.

    Drives the planning queue: the planning screen lists ``UNPLANNED``
    shipments. Creating a trip plan moves a shipment to ``PLANNED`` and
    deleting that trip plan moves it back. Completing the trip moves it to
    ``COMPLETED``.
    """

    UNPLANNED = "unplanned"
    PLANNED = "planned"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class DocumentParseStatus(StrEnum):
    """Outcome of extracting structured fields from an uploaded document."""

    PENDING = "pending"
    PARSED = "parsed"
    FAILED = "failed"
