from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import computed_field
from sqlmodel import Field, SQLModel

from app.fleet.models import VehicleFuelType, VehicleStatus, VehicleType, _d


class VehicleCreate(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    unit_number: str = Field(min_length=1, max_length=64)
    status: VehicleStatus = VehicleStatus.ACTIVE
    vehicle_type: VehicleType
    make: str | None = Field(default=None, max_length=255)
    model: str | None = Field(default=None, max_length=255)
    year: int | None = Field(default=None, ge=1900, le=3000)
    height_in: int | None = Field(
        default=None, ge=1, le=1968, description=_d("height_in")
    )
    width_in: int | None = Field(
        default=None, ge=1, le=1968, description=_d("width_in")
    )
    length_in: int | None = Field(
        default=None, ge=1, le=11811, description=_d("length_in")
    )
    gross_weight_lbs: int | None = Field(
        default=None, ge=1, le=2_000_000, description=_d("gross_weight_lbs")
    )
    weight_per_axle_lbs: int | None = Field(
        default=None, ge=1, le=2_000_000, description=_d("weight_per_axle_lbs")
    )
    axle_count: int | None = Field(
        default=None, ge=2, le=255, description=_d("axle_count")
    )
    tires_count: int | None = Field(
        default=None, ge=1, le=255, description=_d("tires_count")
    )
    trailer_count: int = Field(default=0, ge=0, le=255, description=_d("trailer_count"))
    trailer_length_in: int | None = Field(
        default=None, ge=1, le=787, description=_d("trailer_length_in")
    )
    kpra_length_in: int | None = Field(
        default=None, ge=1, le=11811, description=_d("kpra_length_in")
    )
    payload_capacity_lbs: int | None = Field(
        default=None, ge=1, le=2_000_000, description=_d("payload_capacity_lbs")
    )
    max_speed_mph: int | None = Field(
        default=None, ge=1, le=156, description=_d("max_speed_mph")
    )
    fuel_type: VehicleFuelType = VehicleFuelType.TRUCK_DIESEL
    tank_capacity_gallons: Decimal = Field(gt=0)
    consumption_mpg: Decimal = Field(gt=0)


class VehicleUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    unit_number: str | None = Field(default=None, min_length=1, max_length=64)
    status: VehicleStatus | None = None
    vehicle_type: VehicleType | None = None
    make: str | None = Field(default=None, max_length=255)
    model: str | None = Field(default=None, max_length=255)
    year: int | None = Field(default=None, ge=1900, le=3000)
    height_in: int | None = Field(
        default=None, ge=1, le=1968, description=_d("height_in")
    )
    width_in: int | None = Field(
        default=None, ge=1, le=1968, description=_d("width_in")
    )
    length_in: int | None = Field(
        default=None, ge=1, le=11811, description=_d("length_in")
    )
    gross_weight_lbs: int | None = Field(
        default=None, ge=1, le=2_000_000, description=_d("gross_weight_lbs")
    )
    weight_per_axle_lbs: int | None = Field(
        default=None, ge=1, le=2_000_000, description=_d("weight_per_axle_lbs")
    )
    axle_count: int | None = Field(
        default=None, ge=2, le=255, description=_d("axle_count")
    )
    tires_count: int | None = Field(
        default=None, ge=1, le=255, description=_d("tires_count")
    )
    trailer_count: int | None = Field(
        default=None, ge=0, le=255, description=_d("trailer_count")
    )
    trailer_length_in: int | None = Field(
        default=None, ge=1, le=787, description=_d("trailer_length_in")
    )
    kpra_length_in: int | None = Field(
        default=None, ge=1, le=11811, description=_d("kpra_length_in")
    )
    payload_capacity_lbs: int | None = Field(
        default=None, ge=1, le=2_000_000, description=_d("payload_capacity_lbs")
    )
    max_speed_mph: int | None = Field(
        default=None, ge=1, le=156, description=_d("max_speed_mph")
    )
    fuel_type: VehicleFuelType | None = None
    tank_capacity_gallons: Decimal | None = Field(default=None, gt=0)
    consumption_mpg: Decimal | None = Field(default=None, gt=0)


class VehiclePublic(SQLModel):
    id: uuid.UUID
    name: str
    unit_number: str
    status: VehicleStatus
    vehicle_type: VehicleType
    make: str | None = None
    model: str | None = None
    year: int | None = None
    height_in: int | None = Field(default=None, description=_d("height_in"))
    width_in: int | None = Field(default=None, description=_d("width_in"))
    length_in: int | None = Field(default=None, description=_d("length_in"))
    gross_weight_lbs: int | None = Field(
        default=None, description=_d("gross_weight_lbs")
    )
    weight_per_axle_lbs: int | None = Field(
        default=None, description=_d("weight_per_axle_lbs")
    )
    axle_count: int | None = Field(default=None, description=_d("axle_count"))
    tires_count: int | None = Field(default=None, description=_d("tires_count"))
    trailer_count: int = Field(default=0, description=_d("trailer_count"))
    trailer_length_in: int | None = Field(
        default=None, description=_d("trailer_length_in")
    )
    kpra_length_in: int | None = Field(default=None, description=_d("kpra_length_in"))
    payload_capacity_lbs: int | None = Field(
        default=None, description=_d("payload_capacity_lbs")
    )
    max_speed_mph: int | None = Field(default=None, description=_d("max_speed_mph"))
    fuel_type: VehicleFuelType
    tank_capacity_gallons: Decimal
    consumption_mpg: Decimal
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[misc]
    @property
    def usable_tank_capacity_gallons(self) -> Decimal:
        """Usable tank capacity is always 95% of tank capacity."""
        return self.tank_capacity_gallons * Decimal("0.95")


class VehiclesPublic(SQLModel):
    data: list[VehiclePublic]
    count: int
