from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlmodel import Field, SQLModel

from app.fleet.models import VehicleFuelType, VehicleStatus, VehicleType


class VehicleFuelProfileCreate(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    fuel_type: VehicleFuelType = VehicleFuelType.TRUCK_DIESEL
    tank_capacity_gallons: Decimal = Field(gt=0)
    usable_tank_capacity_gallons: Decimal = Field(gt=0)
    consumption_mpg: Decimal = Field(gt=0)
    reserve_gallons: Decimal = Field(ge=0)
    min_refuel_gallons: Decimal | None = Field(default=None, ge=0)
    max_refuel_gallons: Decimal | None = Field(default=None, gt=0)


class VehicleFuelProfileUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    fuel_type: VehicleFuelType | None = None
    tank_capacity_gallons: Decimal | None = Field(default=None, gt=0)
    usable_tank_capacity_gallons: Decimal | None = Field(default=None, gt=0)
    consumption_mpg: Decimal | None = Field(default=None, gt=0)
    reserve_gallons: Decimal | None = Field(default=None, ge=0)
    min_refuel_gallons: Decimal | None = Field(default=None, ge=0)
    max_refuel_gallons: Decimal | None = Field(default=None, gt=0)


class VehicleFuelProfilePublic(SQLModel):
    id: uuid.UUID
    name: str
    fuel_type: VehicleFuelType
    tank_capacity_gallons: Decimal
    usable_tank_capacity_gallons: Decimal
    consumption_mpg: Decimal
    reserve_gallons: Decimal
    min_refuel_gallons: Decimal | None = None
    max_refuel_gallons: Decimal | None = None
    created_at: datetime
    updated_at: datetime


class VehicleCreate(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    unit_number: str = Field(min_length=1, max_length=64)
    status: VehicleStatus = VehicleStatus.ACTIVE
    vehicle_type: VehicleType
    make: str | None = Field(default=None, max_length=255)
    model: str | None = Field(default=None, max_length=255)
    year: int | None = Field(default=None, ge=1900, le=3000)
    routing_profile_id: uuid.UUID | None = None
    fuel_profile: VehicleFuelProfileCreate


class VehicleUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    unit_number: str | None = Field(default=None, min_length=1, max_length=64)
    status: VehicleStatus | None = None
    vehicle_type: VehicleType | None = None
    make: str | None = Field(default=None, max_length=255)
    model: str | None = Field(default=None, max_length=255)
    year: int | None = Field(default=None, ge=1900, le=3000)
    routing_profile_id: uuid.UUID | None = None
    fuel_profile: VehicleFuelProfileUpdate | None = None


class VehiclePublic(SQLModel):
    id: uuid.UUID
    name: str
    unit_number: str
    status: VehicleStatus
    vehicle_type: VehicleType
    make: str | None = None
    model: str | None = None
    year: int | None = None
    routing_profile_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    fuel_profile: VehicleFuelProfilePublic


class VehiclesPublic(SQLModel):
    data: list[VehiclePublic]
    count: int
