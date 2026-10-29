"""Data access for trip plans."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import cast
from sqlalchemy import func as sa_func
from sqlmodel import Session, col, func, or_, select

from app.core.datetime import get_datetime_utc
from app.fuel_optimization.models import FuelOptimizationRun, FuelOptimizationStop
from app.map.models import FuelStation
from app.trip_plans.domain import TripPlanStatus
from app.trip_plans.models import TripPlan


@dataclass(frozen=True)
class OptimizationStopRow:
    """A persisted optimizer stop joined with its station coordinates."""

    sequence: int
    station_id: uuid.UUID
    name: str
    longitude: Decimal
    latitude: Decimal
    route_offset_meters: Decimal
    fuel_before_gallons: Decimal
    fuel_added_gallons: Decimal
    fuel_after_gallons: Decimal
    fuel_price_per_gallon: Decimal
    fuel_cost: Decimal
    detour_distance_meters: Decimal
    detour_time_seconds: int


class OptimizationRunQueryRepository:
    """Read-only access to optimizer output needed to build a trip plan."""

    def __init__(self, session: Session):
        self.session = session

    def get_run(self, run_id: uuid.UUID) -> FuelOptimizationRun | None:
        statement = select(FuelOptimizationRun).where(FuelOptimizationRun.id == run_id)
        return self.session.exec(statement).first()

    def list_stops(self, run_id: uuid.UUID) -> list[OptimizationStopRow]:
        """Return the optimizer stops with coordinates, ordered by sequence."""
        location = cast(
            FuelStation.location, Geometry(geometry_type="POINT", srid=4326)
        )
        statement = (
            select(  # type: ignore[call-overload]  # ty: ignore[no-matching-overload]
                FuelOptimizationStop.sequence,
                FuelOptimizationStop.station_id,
                FuelStation.name,
                sa_func.ST_X(location).label("longitude"),
                sa_func.ST_Y(location).label("latitude"),
                FuelOptimizationStop.route_offset_meters,
                FuelOptimizationStop.fuel_before_gallons,
                FuelOptimizationStop.fuel_added_gallons,
                FuelOptimizationStop.fuel_after_gallons,
                FuelOptimizationStop.fuel_price_per_gallon,
                FuelOptimizationStop.fuel_cost,
                FuelOptimizationStop.detour_distance_meters,
                FuelOptimizationStop.detour_time_seconds,
            )
            .join(FuelStation, col(FuelOptimizationStop.station_id) == FuelStation.id)
            .where(FuelOptimizationStop.optimization_run_id == run_id)
            .order_by(col(FuelOptimizationStop.sequence))
        )
        return [
            OptimizationStopRow(
                sequence=row[0],
                station_id=row[1],
                name=row[2],
                longitude=Decimal(str(row[3])),
                latitude=Decimal(str(row[4])),
                route_offset_meters=row[5],
                fuel_before_gallons=row[6],
                fuel_added_gallons=row[7],
                fuel_after_gallons=row[8],
                fuel_price_per_gallon=row[9],
                fuel_cost=row[10],
                detour_distance_meters=row[11],
                detour_time_seconds=row[12],
            )
            for row in self.session.exec(statement).all()
        ]


class TripPlanRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, trip_plan: TripPlan) -> TripPlan:
        self.session.add(trip_plan)
        self.session.commit()
        self.session.refresh(trip_plan)
        return trip_plan

    def get(self, trip_plan_id: uuid.UUID) -> TripPlan | None:
        statement = select(TripPlan).where(TripPlan.id == trip_plan_id)
        return self.session.exec(statement).first()

    def get_by_share_token(self, share_token: str) -> TripPlan | None:
        statement = select(TripPlan).where(TripPlan.share_token == share_token)
        return self.session.exec(statement).first()

    def list_for_owner(
        self, owner_id: uuid.UUID, *, skip: int = 0, limit: int = 100
    ) -> list[TripPlan]:
        statement = (
            select(TripPlan)
            .where(TripPlan.owner_id == owner_id)
            .order_by(col(TripPlan.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.session.exec(statement).all())

    def count_for_owner(self, owner_id: uuid.UUID) -> int:
        statement = (
            select(func.count())
            .select_from(TripPlan)
            .where(TripPlan.owner_id == owner_id)
        )
        return self.session.exec(statement).one()

    def list_all(self, *, skip: int = 0, limit: int = 100) -> list[TripPlan]:
        statement = (
            select(TripPlan)
            .order_by(col(TripPlan.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.session.exec(statement).all())

    def count_all(self) -> int:
        statement = select(func.count()).select_from(TripPlan)
        return self.session.exec(statement).one()

    def list_for_driver(
        self, driver_id: uuid.UUID, *, skip: int = 0, limit: int = 100
    ) -> list[TripPlan]:
        statement = (
            select(TripPlan)
            .where(TripPlan.assigned_driver_id == driver_id)
            .order_by(col(TripPlan.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.session.exec(statement).all())

    def count_for_driver(self, driver_id: uuid.UUID) -> int:
        statement = (
            select(func.count())
            .select_from(TripPlan)
            .where(TripPlan.assigned_driver_id == driver_id)
        )
        return self.session.exec(statement).one()

    def list_accessible(
        self, user_id: uuid.UUID, *, skip: int = 0, limit: int = 100
    ) -> list[TripPlan]:
        statement = (
            select(TripPlan)
            .where(
                or_(
                    TripPlan.owner_id == user_id,
                    TripPlan.assigned_driver_id == user_id,
                )
            )
            .order_by(col(TripPlan.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.session.exec(statement).all())

    def count_accessible(self, user_id: uuid.UUID) -> int:
        statement = (
            select(func.count())
            .select_from(TripPlan)
            .where(
                or_(
                    TripPlan.owner_id == user_id,
                    TripPlan.assigned_driver_id == user_id,
                )
            )
        )
        return self.session.exec(statement).one()

    def update(self, trip_plan: TripPlan, **fields: Any) -> TripPlan:
        for name, value in fields.items():
            setattr(trip_plan, name, value)
        trip_plan.updated_at = get_datetime_utc()
        self.session.add(trip_plan)
        self.session.commit()
        self.session.refresh(trip_plan)
        return trip_plan

    def set_refined_route(
        self,
        trip_plan: TripPlan,
        *,
        refined_route_id: uuid.UUID,
        refined_provider: str,
        refined_distance_meters: int,
        refined_duration_seconds: int,
    ) -> TripPlan:
        return self.update(
            trip_plan,
            refined_route_id=refined_route_id,
            refined_provider=refined_provider,
            refined_distance_meters=refined_distance_meters,
            refined_duration_seconds=refined_duration_seconds,
            refine_error=None,
            status=(
                TripPlanStatus.REFINED
                if trip_plan.status
                in (TripPlanStatus.DRAFT, TripPlanStatus.REFINE_FAILED)
                else trip_plan.status
            ),
        )

    def set_refine_error(self, trip_plan: TripPlan, message: str) -> TripPlan:
        return self.update(
            trip_plan,
            status=TripPlanStatus.REFINE_FAILED,
            refine_error=message[:512],
        )

    def delete(self, trip_plan: TripPlan) -> None:
        self.session.delete(trip_plan)
        self.session.commit()
