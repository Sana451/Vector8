"""Persistence model for trip plans.

A trip plan ties together the three records that already exist for a planned
run: the base route calculation, the fuel optimization run and the refined
route calculation produced by sending the selected fuel stops back to the
routing provider as waypoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String
from sqlmodel import Column, Field, SQLModel

from app.core.datetime import get_datetime_utc
from app.trip_plans.domain import TripPlanStatus


class TripPlan(SQLModel, table=True):
    __tablename__ = "trip_plans"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(sa_column=Column(String(length=255), nullable=False))
    owner_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    assigned_driver_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True
        ),
    )
    assigned_by_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )
    assigned_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    vehicle_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    base_route_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("route_calculations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    optimization_run_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("fuel_optimization_runs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    refined_route_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("route_calculations.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    refined_provider: str | None = Field(
        default=None, sa_column=Column(String(length=32), nullable=True)
    )
    origin_label: str | None = Field(
        default=None, sa_column=Column(String(length=512), nullable=True)
    )
    destination_label: str | None = Field(
        default=None, sa_column=Column(String(length=512), nullable=True)
    )
    status: TripPlanStatus = Field(
        default=TripPlanStatus.DRAFT,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    stops_snapshot: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    base_distance_meters: int = Field(sa_column=Column(BigInteger, nullable=False))
    base_duration_seconds: int = Field(sa_column=Column(Integer, nullable=False))
    refined_distance_meters: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    refined_duration_seconds: int | None = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    refine_error: str | None = Field(
        default=None, sa_column=Column(String(length=512), nullable=True)
    )
    share_token: str | None = Field(
        default=None,
        sa_column=Column(String(length=64), nullable=True, unique=True, index=True),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
