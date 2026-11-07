"""Last known position of a fleet vehicle.

Positions are a *hint*, never a fact the planner depends on. Today nothing
writes them automatically: the fleet has no telematics feed yet, so the table
exists so that dispatchers can record a position by hand and so that the
upcoming sensor integration has a place to land.

Two things follow from treating a position as a hint:

* every reading carries ``recorded_at`` and ``source``, so a consumer can
  decide for itself whether a reading is too old to trust;
* readings are append-only. The newest row per vehicle is the current
  position, and the history stays available for the planned cross-check
  against the vehicle's last completed trip.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from geoalchemy2 import Geography
from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlmodel import Column, Field, SQLModel

from app.core.datetime import get_datetime_utc


class VehiclePositionSource(StrEnum):
    """Where a reading came from, which decides how much to trust it."""

    MANUAL = "manual"
    """A dispatcher typed it in."""

    TRIP = "trip"
    """Derived from the destination of the vehicle's last completed trip."""

    SENSOR = "sensor"
    """Reported by on-board telematics. Not wired up yet."""


class VehiclePosition(SQLModel, table=True):
    __tablename__ = "vehicle_positions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    vehicle_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    location: str = Field(
        sa_column=Column(
            Geography(geometry_type="POINT", srid=4326),
            nullable=False,
        )
    )
    source: VehiclePositionSource = Field(
        sa_column=Column(String(length=16), nullable=False)
    )
    label: str | None = Field(
        default=None, sa_column=Column(String(length=512), nullable=True)
    )
    # The completed trip that produced a TRIP reading.
    trip_plan_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            Uuid(),
            ForeignKey("trip_plans.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    recorded_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
