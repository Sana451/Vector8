from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlmodel import Column, Field, SQLModel

from app.core.datetime import get_datetime_utc
from app.fuel_optimization.domain import (
    FuelOptimizationAlgorithm,
    FuelOptimizationStatus,
)


class FuelOptimizationRun(SQLModel, table=True):
    __tablename__ = "fuel_optimization_runs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    route_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("route_calculations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    vehicle_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    algorithm: FuelOptimizationAlgorithm = Field(
        sa_column=Column(String(length=32), nullable=False)
    )
    algorithm_version: str = Field(max_length=32)
    status: FuelOptimizationStatus = Field(
        sa_column=Column(String(length=32), nullable=False)
    )
    initial_fuel_gallons: Decimal = Field(
        sa_column=Column(Numeric(10, 4), nullable=False)
    )
    total_fuel_consumed_gallons: Decimal = Field(
        sa_column=Column(Numeric(10, 4), nullable=False)
    )
    total_fuel_purchased_gallons: Decimal = Field(
        sa_column=Column(Numeric(10, 4), nullable=False)
    )
    total_fuel_cost: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    total_detour_distance_meters: Decimal = Field(
        sa_column=Column(Numeric(12, 2), nullable=False)
    )
    total_detour_time_seconds: int = Field(sa_column=Column(Integer, nullable=False))
    number_of_stops: int = Field(sa_column=Column(Integer, nullable=False))
    remaining_fuel_gallons: Decimal = Field(
        sa_column=Column(Numeric(10, 4), nullable=False)
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class FuelOptimizationStop(SQLModel, table=True):
    __tablename__ = "fuel_optimization_stops"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    optimization_run_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("fuel_optimization_runs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    sequence: int = Field(sa_column=Column(Integer, nullable=False))
    station_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("fuel_stations.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        )
    )
    route_offset_meters: Decimal = Field(
        sa_column=Column(Numeric(12, 2), nullable=False)
    )
    fuel_before_gallons: Decimal = Field(
        sa_column=Column(Numeric(10, 4), nullable=False)
    )
    fuel_added_gallons: Decimal = Field(
        sa_column=Column(Numeric(10, 4), nullable=False)
    )
    fuel_after_gallons: Decimal = Field(
        sa_column=Column(Numeric(10, 4), nullable=False)
    )
    fuel_price_per_gallon: Decimal = Field(
        sa_column=Column(Numeric(10, 4), nullable=False)
    )
    fuel_cost: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    detour_distance_meters: Decimal = Field(
        sa_column=Column(Numeric(12, 2), nullable=False)
    )
    detour_time_seconds: int = Field(sa_column=Column(Integer, nullable=False))
