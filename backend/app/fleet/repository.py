from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlmodel import Session, col, func, select

from app.core.datetime import get_datetime_utc
from app.core.logging import get_logger
from app.fleet.models import Vehicle
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

    def get_by_unit_number(self, unit_number: str) -> Vehicle | None:
        statement = select(Vehicle).where(Vehicle.unit_number == unit_number)
        return self.session.exec(statement).first()

    def create(self, vehicle_in: VehicleCreate) -> Vehicle:
        now = get_datetime_utc()
        vehicle = Vehicle.model_validate(
            vehicle_in.model_dump(),
            update={"created_at": now, "updated_at": now},
        )
        self.session.add(vehicle)
        self.session.commit()
        self.session.refresh(vehicle)
        return vehicle

    def update(self, vehicle: Vehicle, vehicle_in: VehicleUpdate) -> Vehicle:
        now = get_datetime_utc()
        vehicle_data = vehicle_in.model_dump(exclude_unset=True)
        vehicle.sqlmodel_update(vehicle_data)
        Vehicle.model_validate(vehicle.model_dump())
        vehicle.updated_at = now

        self.session.add(vehicle)
        self.session.commit()
        self.session.refresh(vehicle)
        return vehicle

    def delete(self, vehicle: Vehicle) -> None:
        self.session.delete(vehicle)
        self.session.commit()
