"""Persistence model for driver profiles.

Kept in its own table rather than as extra columns on ``User`` so the fields a
dispatcher never fills in do not clutter every user record.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlmodel import Column, Field, SQLModel

from app.core.datetime import get_datetime_utc

MAX_PHONE_LENGTH = 32
MAX_LICENSE_LENGTH = 64


class DriverProfile(SQLModel, table=True):
    __tablename__ = "driver_profiles"

    user_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("user.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )
    phone: str | None = Field(
        default=None, sa_column=Column(String(length=MAX_PHONE_LENGTH), nullable=True)
    )
    license_number: str | None = Field(
        default=None, sa_column=Column(String(length=MAX_LICENSE_LENGTH), nullable=True)
    )
    default_vehicle_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True, index=True
        ),
    )
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
