from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlmodel import Session, col, func, select

from app.core.datetime import get_datetime_utc
from app.core.logging import get_logger
from app.fleet.models import Vehicle, VehicleFuelProfile
from app.fleet.schemas import VehicleCreate, VehicleUpdate

logger = get_logger(__name__)


class VehicleRepository:
    def __init__(self, session: Session):
        self.session = session

    def list(self, *, skip: int = 0, limit: int = 100) -> tuple[Sequence[Vehicle], int]:
        count = int(self.session.exec(select(func.count()).select_from(Vehicle)).one())
        statement = (
            select(Vehicle)
            .order_by(col(Vehicle.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.session.exec(statement).all()), count

    def get(self, vehicle_id: uuid.UUID) -> Vehicle | None:
        return self.session.get(Vehicle, vehicle_id)

    def get_fuel_profile(self, fuel_profile_id: uuid.UUID) -> VehicleFuelProfile | None:
        return self.session.get(VehicleFuelProfile, fuel_profile_id)

    def get_by_unit_number(self, unit_number: str) -> Vehicle | None:
        statement = select(Vehicle).where(Vehicle.unit_number == unit_number)
        return self.session.exec(statement).first()

    def create(self, vehicle_in: VehicleCreate) -> Vehicle:
        now = get_datetime_utc()
        profile = VehicleFuelProfile.model_validate(vehicle_in.fuel_profile)
        profile.created_at = now
        profile.updated_at = now
        self.session.add(profile)
        self.session.flush()

        vehicle = Vehicle.model_validate(
            vehicle_in.model_dump(exclude={"fuel_profile"}),
            update={
                "fuel_profile_id": profile.id,
                "created_at": now,
                "updated_at": now,
            },
        )
        self.session.add(vehicle)
        self.session.commit()
        self.session.refresh(vehicle)
        self.session.refresh(profile)
        return vehicle

    def update(self, vehicle: Vehicle, vehicle_in: VehicleUpdate) -> Vehicle:
        now = get_datetime_utc()
        vehicle_data = vehicle_in.model_dump(
            exclude_unset=True, exclude={"fuel_profile"}
        )
        vehicle.sqlmodel_update(vehicle_data)
        vehicle.updated_at = now

        if vehicle_in.fuel_profile is not None:
            profile = self.session.get(VehicleFuelProfile, vehicle.fuel_profile_id)
            if profile is None:
                raise ValueError("Vehicle fuel profile not found")
            profile.sqlmodel_update(
                vehicle_in.fuel_profile.model_dump(exclude_unset=True)
            )
            VehicleFuelProfile.model_validate(profile.model_dump())
            profile.updated_at = now
            self.session.add(profile)

        self.session.add(vehicle)
        self.session.commit()
        self.session.refresh(vehicle)
        return vehicle

    def delete(self, vehicle: Vehicle) -> None:
        profile = self.session.get(VehicleFuelProfile, vehicle.fuel_profile_id)
        self.session.delete(vehicle)
        if profile is not None:
            self.session.delete(profile)
        self.session.commit()
