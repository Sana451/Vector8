"""Schemas for vehicle positions."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.fleet.positions import VehiclePositionSource


class VehiclePositionCreate(BaseModel):
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    label: str | None = Field(default=None, max_length=512)
    recorded_at: datetime | None = Field(
        default=None,
        description="When the vehicle was there. Defaults to now.",
    )


class VehiclePositionPublic(BaseModel):
    vehicle_id: uuid.UUID
    longitude: float
    latitude: float
    source: VehiclePositionSource
    label: str | None = None
    recorded_at: datetime
