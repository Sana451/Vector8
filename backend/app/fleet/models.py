from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import model_validator
from sqlalchemy import DateTime, Numeric, String
from sqlmodel import Column, Field, SQLModel

from app.core.datetime import get_datetime_utc


class VehicleStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"


class VehicleType(StrEnum):
    TRACTOR = "tractor"
    TRUCK = "truck"


class VehicleFuelType(StrEnum):
    TRUCK_DIESEL = "truck_diesel"


class VehicleFuelProfileBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    fuel_type: VehicleFuelType = Field(
        default=VehicleFuelType.TRUCK_DIESEL,
        sa_column=Column(String(length=64), nullable=False),
    )
    tank_capacity_gallons: Decimal = Field(
        sa_column=Column(Numeric(10, 4), nullable=False)
    )
    usable_tank_capacity_gallons: Decimal = Field(
        sa_column=Column(Numeric(10, 4), nullable=False)
    )
    consumption_mpg: Decimal = Field(sa_column=Column(Numeric(8, 3), nullable=False))
    reserve_gallons: Decimal = Field(sa_column=Column(Numeric(10, 4), nullable=False))
    min_refuel_gallons: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(10, 4), nullable=True),
    )
    max_refuel_gallons: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(10, 4), nullable=True),
    )

    @model_validator(mode="after")
    def validate_invariants(self) -> VehicleFuelProfileBase:
        if self.tank_capacity_gallons <= 0:
            raise ValueError("tank_capacity_gallons must be greater than 0")
        if self.usable_tank_capacity_gallons <= 0:
            raise ValueError("usable_tank_capacity_gallons must be greater than 0")
        if self.usable_tank_capacity_gallons > self.tank_capacity_gallons:
            raise ValueError(
                "usable_tank_capacity_gallons must be less than or equal to tank_capacity_gallons"
            )
        if self.consumption_mpg <= 0:
            raise ValueError("consumption_mpg must be greater than 0")
        if self.reserve_gallons < 0:
            raise ValueError("reserve_gallons must be greater than or equal to 0")
        if self.reserve_gallons >= self.usable_tank_capacity_gallons:
            raise ValueError(
                "reserve_gallons must be less than usable_tank_capacity_gallons"
            )
        if self.min_refuel_gallons is not None and self.min_refuel_gallons < 0:
            raise ValueError("min_refuel_gallons must be greater than or equal to 0")
        if self.max_refuel_gallons is not None and self.max_refuel_gallons <= 0:
            raise ValueError("max_refuel_gallons must be greater than 0")
        if (
            self.min_refuel_gallons is not None
            and self.max_refuel_gallons is not None
            and self.min_refuel_gallons > self.max_refuel_gallons
        ):
            raise ValueError(
                "min_refuel_gallons must be less than or equal to max_refuel_gallons"
            )
        return self


class VehicleFuelProfile(VehicleFuelProfileBase, table=True):
    __tablename__ = "vehicle_fuel_profiles"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class VehicleBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    unit_number: str = Field(min_length=1, max_length=64, index=True, unique=True)
    status: VehicleStatus = Field(
        default=VehicleStatus.ACTIVE,
        sa_column=Column(String(length=32), nullable=False),
    )
    vehicle_type: VehicleType = Field(
        sa_column=Column(String(length=32), nullable=False)
    )
    make: str | None = Field(default=None, max_length=255)
    model: str | None = Field(default=None, max_length=255)
    year: int | None = Field(default=None, ge=1900, le=3000)
    routing_profile_id: uuid.UUID | None = Field(default=None, index=True)


class Vehicle(VehicleBase, table=True):
    __tablename__ = "vehicles"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    fuel_profile_id: uuid.UUID = Field(
        foreign_key="vehicle_fuel_profiles.id", nullable=False, index=True
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
