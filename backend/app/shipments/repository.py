"""Data access for shipments, their stops and their documents."""

from __future__ import annotations

import uuid

from geoalchemy2 import Geometry
from sqlalchemy import cast
from sqlalchemy import func as sa_func
from sqlmodel import Session, col, func, select

from app.providers.geo import GeoJSONPoint
from app.shipments.domain import PlanningStatus
from app.shipments.models import Shipment, ShipmentDocument, ShipmentStop


def stop_location_to_point(
    longitude: float | None, latitude: float | None
) -> GeoJSONPoint | None:
    """Build a GeoJSON point from PostGIS accessor output."""
    if longitude is None or latitude is None:
        return None
    return GeoJSONPoint(coordinates=(float(longitude), float(latitude)))


class ShipmentRepository:
    """Reads and writes shipment aggregates."""

    def __init__(self, session: Session):
        self.session = session

    def get(self, shipment_id: uuid.UUID) -> Shipment | None:
        statement = select(Shipment).where(Shipment.id == shipment_id)
        return self.session.exec(statement).first()

    def list_for_owner(
        self,
        owner_id: uuid.UUID,
        *,
        planning_status: PlanningStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Shipment], int]:
        """Return a page of the owner's shipments and the total count."""
        filters = [col(Shipment.owner_id) == owner_id]
        if planning_status is not None:
            filters.append(col(Shipment.planning_status) == planning_status)

        count_statement = select(func.count()).select_from(Shipment).where(*filters)
        total = self.session.exec(count_statement).one()

        statement = (
            select(Shipment)
            .where(*filters)
            .order_by(col(Shipment.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.session.exec(statement).all()), total

    def list_stops(self, shipment_id: uuid.UUID) -> list[ShipmentStop]:
        statement = (
            select(ShipmentStop)
            .where(col(ShipmentStop.shipment_id) == shipment_id)
            .order_by(col(ShipmentStop.sequence))
        )
        return list(self.session.exec(statement).all())

    def list_stops_with_points(
        self, shipment_id: uuid.UUID
    ) -> list[tuple[ShipmentStop, GeoJSONPoint | None]]:
        """Return stops with their coordinates, ordered by sequence.

        Coordinates come from PostGIS accessors rather than from the loaded
        ``Geography`` value, which would need shapely to decode.
        """
        location = cast(
            ShipmentStop.location, Geometry(geometry_type="POINT", srid=4326)
        )
        statement = (
            select(
                ShipmentStop,
                sa_func.ST_X(location).label("longitude"),
                sa_func.ST_Y(location).label("latitude"),
            )
            .where(col(ShipmentStop.shipment_id) == shipment_id)
            .order_by(col(ShipmentStop.sequence))
        )
        return [
            (stop, stop_location_to_point(longitude, latitude))
            for stop, longitude, latitude in self.session.exec(statement).all()
        ]

    def list_stop_points(
        self, shipment_id: uuid.UUID
    ) -> list[tuple[int, GeoJSONPoint | None]]:
        """Return ``(sequence, point)`` pairs ordered by sequence.

        Planning only needs the coordinates, so these are read with PostGIS
        accessors rather than by loading whole stop rows.
        """
        location = cast(
            ShipmentStop.location, Geometry(geometry_type="POINT", srid=4326)
        )
        statement = (
            select(
                ShipmentStop.sequence,
                sa_func.ST_X(location).label("longitude"),
                sa_func.ST_Y(location).label("latitude"),
            )
            .where(col(ShipmentStop.shipment_id) == shipment_id)
            .order_by(col(ShipmentStop.sequence))
        )
        return [
            (sequence, stop_location_to_point(longitude, latitude))
            for sequence, longitude, latitude in self.session.exec(statement).all()
        ]

    def delete_stops(self, shipment_id: uuid.UUID) -> None:
        for stop in self.list_stops(shipment_id):
            self.session.delete(stop)
        self.session.flush()

    def list_documents(self, shipment_id: uuid.UUID) -> list[ShipmentDocument]:
        statement = (
            select(ShipmentDocument)
            .where(col(ShipmentDocument.shipment_id) == shipment_id)
            .order_by(col(ShipmentDocument.uploaded_at).desc())
        )
        return list(self.session.exec(statement).all())

    def get_document(self, document_id: uuid.UUID) -> ShipmentDocument | None:
        statement = select(ShipmentDocument).where(ShipmentDocument.id == document_id)
        return self.session.exec(statement).first()

    def find_shipment_by_content_hash(
        self, owner_id: uuid.UUID, content_sha256: str
    ) -> Shipment | None:
        """Return the shipment an identical upload already produced, if any.

        Re-sending the same PDF is a routine accident in dispatch work, and a
        duplicate shipment is worse than none: it can be planned by mistake.
        """
        statement = (
            select(Shipment)
            .join(ShipmentDocument, col(ShipmentDocument.shipment_id) == Shipment.id)
            .where(
                col(Shipment.owner_id) == owner_id,
                col(ShipmentDocument.content_sha256) == content_sha256,
            )
            .order_by(col(Shipment.created_at).desc())
        )
        return self.session.exec(statement).first()

    def add(self, instance: Shipment | ShipmentStop | ShipmentDocument) -> None:
        self.session.add(instance)

    def delete(self, shipment: Shipment) -> None:
        self.session.delete(shipment)

    def commit(self) -> None:
        self.session.commit()

    def refresh(self, instance: Shipment | ShipmentStop | ShipmentDocument) -> None:
        self.session.refresh(instance)
