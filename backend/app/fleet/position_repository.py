"""Queries over vehicle position readings."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from geoalchemy2 import Geography, Geometry
from sqlalchemy import case, cast, null, select
from sqlalchemy import func as sa_func
from sqlmodel import Session, col

from app.fleet.positions import VehiclePosition, VehiclePositionSource


@dataclass(frozen=True)
class PositionReading:
    vehicle_id: uuid.UUID
    longitude: float
    latitude: float
    source: VehiclePositionSource
    label: str | None
    recorded_at: datetime
    distance_meters: float | None = None


class VehiclePositionRepository:
    def __init__(self, session: Session):
        self.session = session

    def has_trip_reading(self, trip_plan_id: uuid.UUID) -> bool:
        statement = (
            select(col(VehiclePosition.id))
            .where(col(VehiclePosition.trip_plan_id) == trip_plan_id)
            .limit(1)
        )
        return self.session.connection().execute(statement).first() is not None

    def add(
        self,
        *,
        vehicle_id: uuid.UUID,
        longitude: float,
        latitude: float,
        source: VehiclePositionSource,
        label: str | None,
        recorded_at: datetime,
        trip_plan_id: uuid.UUID | None = None,
        commit: bool = True,
    ) -> VehiclePosition:
        position = VehiclePosition(
            vehicle_id=vehicle_id,
            location=f"SRID=4326;POINT({longitude} {latitude})",
            source=source,
            label=label,
            recorded_at=recorded_at,
            trip_plan_id=trip_plan_id,
        )
        self.session.add(position)
        if commit:
            self.session.commit()
            self.session.refresh(position)
        return position

    def latest(
        self,
        *,
        vehicle_ids: list[uuid.UUID] | None = None,
        distance_to: tuple[float, float] | None = None,
    ) -> dict[uuid.UUID, PositionReading]:
        """Return the best reading per vehicle.

        Sources are ranked as a fallback chain: a sensor reading beats the
        destination of the last completed trip, which beats a manual entry.
        Within a source the newest reading wins.

        When ``distance_to`` (longitude, latitude) is given, each reading also
        carries the geodesic distance to that point, computed by PostGIS.
        """
        source_rank = case(
            (col(VehiclePosition.source) == VehiclePositionSource.SENSOR.value, 0),
            (col(VehiclePosition.source) == VehiclePositionSource.TRIP.value, 1),
            else_=2,
        )
        geometry = cast(VehiclePosition.location, Geometry("POINT", srid=4326))
        distance: Any = null()
        if distance_to is not None:
            target = cast(
                sa_func.ST_SetSRID(
                    sa_func.ST_MakePoint(distance_to[0], distance_to[1]), 4326
                ),
                Geography("POINT", srid=4326),
            )
            distance = sa_func.ST_Distance(VehiclePosition.location, target)

        statement = (
            select(
                col(VehiclePosition.vehicle_id),
                sa_func.ST_X(geometry),
                sa_func.ST_Y(geometry),
                col(VehiclePosition.source),
                col(VehiclePosition.label),
                col(VehiclePosition.recorded_at),
                distance,
            )
            .distinct(col(VehiclePosition.vehicle_id))
            .order_by(
                col(VehiclePosition.vehicle_id),
                source_rank,
                col(VehiclePosition.recorded_at).desc(),
            )
        )
        if vehicle_ids is not None:
            statement = statement.where(
                col(VehiclePosition.vehicle_id).in_(vehicle_ids)
            )

        readings: dict[uuid.UUID, PositionReading] = {}
        for row in self.session.connection().execute(statement).all():
            vehicle_id, longitude, latitude, source, label, recorded_at, dist = row
            readings[vehicle_id] = PositionReading(
                vehicle_id=vehicle_id,
                longitude=float(longitude),
                latitude=float(latitude),
                source=VehiclePositionSource(source),
                label=label,
                recorded_at=recorded_at,
                distance_meters=float(dist) if distance_to is not None else None,
            )
        return readings
