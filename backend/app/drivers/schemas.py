"""Request and response schemas for drivers."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field

from app.drivers.models import MAX_LICENSE_LENGTH, MAX_PHONE_LENGTH


class DriverProfileUpdate(BaseModel):
    phone: str | None = Field(default=None, max_length=MAX_PHONE_LENGTH)
    license_number: str | None = Field(default=None, max_length=MAX_LICENSE_LENGTH)
    default_vehicle_id: uuid.UUID | None = None
    notes: str | None = None


class DriverProfilePublic(BaseModel):
    phone: str | None = None
    license_number: str | None = None
    default_vehicle_id: uuid.UUID | None = None
    notes: str | None = None


class DriverPublic(BaseModel):
    """A driver as the dispatcher sees them: account plus profile."""

    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    is_active: bool
    profile: DriverProfilePublic | None = None


class DriversPublic(BaseModel):
    data: list[DriverPublic]
    count: int
