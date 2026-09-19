"""
Map layer repositories.

Persistence and spatial queries for cached map layer data. Route geometry acts
as the skeleton: fuel stations and truck restrictions are selected with
``ST_DWithin`` against the stored corridor.

All reads apply lazy TTL invalidation - expired rows are simply not returned.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlmodel import Session, select

from app.core.logging import get_logger
from app.map.models import FuelStation, TrafficSnapshot, TruckRestriction
from app.providers.geo import Coordinate, linestring_to_wkt

logger = get_logger(__name__)


def get_datetime_utc() -> datetime:
    """Get current datetime in UTC with timezone awareness."""
    return datetime.now(UTC)


class TrafficSnapshotRepository:
    """Repository for cached traffic snapshots."""

    def __init__(self, session: Session):
        """Initialize repository.

        Args:
            session: SQLModel session for database operations.
        """
        self.session = session

    def get_valid(
        self,
        provider: str,
        request_hash: str,
    ) -> TrafficSnapshot | None:
        """Get a non-expired snapshot.

        Args:
            provider: Traffic provider name.
            request_hash: Hash of the corridor query.

        Returns:
            Snapshot if present and fresh, otherwise None.
        """
        statement = select(TrafficSnapshot).where(
            (TrafficSnapshot.provider == provider)
            & (TrafficSnapshot.request_hash == request_hash)
        )
        snapshot = self.session.exec(statement).first()

        if snapshot is None:
            return None

        if snapshot.expires_at < datetime.now(UTC):
            logger.info(
                "Traffic snapshot cache expired",
                provider=provider,
                request_hash=request_hash,
            )
            return None

        return snapshot

    def upsert(
        self,
        provider: str,
        request_hash: str,
        payload: dict,
        ttl_seconds: int,
        coordinates: list[Coordinate] | None = None,
    ) -> TrafficSnapshot:
        """Insert or refresh a traffic snapshot.

        Args:
            provider: Traffic provider name.
            request_hash: Hash of the corridor query.
            payload: Serialized ``TrafficLayerData``.
            ttl_seconds: Cache lifetime in seconds.
            coordinates: Optional route geometry for spatial debugging.

        Returns:
            Persisted snapshot.
        """
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=ttl_seconds)
        geometry = (
            linestring_to_wkt(coordinates)
            if coordinates and len(coordinates) >= 2
            else None
        )

        statement = select(TrafficSnapshot).where(
            (TrafficSnapshot.provider == provider)
            & (TrafficSnapshot.request_hash == request_hash)
        )
        existing = self.session.exec(statement).first()

        try:
            if existing is not None:
                existing.payload = payload
                existing.geometry = geometry
                existing.created_at = now
                existing.expires_at = expires_at
                snapshot = existing
            else:
                snapshot = TrafficSnapshot(
                    provider=provider,
                    request_hash=request_hash,
                    geometry=geometry,
                    payload=payload,
                    created_at=now,
                    expires_at=expires_at,
                )

            self.session.add(snapshot)
            self.session.commit()
            self.session.refresh(snapshot)
            return snapshot
        except Exception as exc:
            logger.error(
                "Error upserting traffic snapshot",
                provider=provider,
                request_hash=request_hash,
                error=str(exc),
                exc_info=True,
            )
            self.session.rollback()
            raise


class _SpatialLayerRepository:
    """Shared ``ST_DWithin`` query logic for point based layers."""

    model: type[FuelStation] | type[TruckRestriction]

    def __init__(self, session: Session):
        """Initialize repository.

        Args:
            session: SQLModel session for database operations.
        """
        self.session = session

    def find_along_route(
        self,
        coordinates: list[Coordinate],
        radius_meters: int,
        limit: int,
        provider: str | None = None,
    ) -> list:
        """Find non-expired rows within ``radius_meters`` of the route.

        Args:
            coordinates: Route geometry as ``[longitude, latitude]`` pairs.
            radius_meters: Search radius in meters.
            limit: Maximum number of rows.
            provider: Optional provider filter.

        Returns:
            Matching rows ordered by distance to the route.
        """
        if len(coordinates) < 2:
            return []

        route = func.ST_GeogFromText(linestring_to_wkt(coordinates).split(";", 1)[1])

        statement = (
            select(self.model)
            .where(func.ST_DWithin(self.model.location, route, radius_meters))
            .where(self.model.expires_at >= datetime.now(UTC))
            .order_by(func.ST_Distance(self.model.location, route))
            .limit(limit)
        )

        if provider is not None:
            statement = statement.where(self.model.provider == provider)

        return list(self.session.exec(statement).all())


class FuelStationRepository(_SpatialLayerRepository):
    """Repository for fuel stations."""

    model = FuelStation

    def upsert_many(
        self,
        provider: str,
        stations: list[dict],
        ttl_seconds: int,
    ) -> int:
        """Insert or refresh fuel stations.

        Args:
            provider: Fuel provider name.
            stations: Rows keyed by ``FuelStation`` column names plus
                ``external_id`` and ``location`` (EWKT).
            ttl_seconds: Cache lifetime in seconds.

        Returns:
            Number of persisted rows.
        """
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=ttl_seconds)

        try:
            for row in stations:
                statement = select(FuelStation).where(
                    (FuelStation.provider == provider)
                    & (FuelStation.external_id == row["external_id"])
                )
                existing = self.session.exec(statement).first()

                if existing is not None:
                    for key, value in row.items():
                        setattr(existing, key, value)
                    existing.created_at = now
                    existing.expires_at = expires_at
                    self.session.add(existing)
                else:
                    self.session.add(
                        FuelStation(
                            provider=provider,
                            created_at=now,
                            expires_at=expires_at,
                            **row,
                        )
                    )

            self.session.commit()
            return len(stations)
        except Exception as exc:
            logger.error(
                "Error upserting fuel stations",
                provider=provider,
                error=str(exc),
                exc_info=True,
            )
            self.session.rollback()
            raise


class TruckRestrictionRepository(_SpatialLayerRepository):
    """Repository for truck restrictions."""

    model = TruckRestriction

    def upsert_many(
        self,
        provider: str,
        restrictions: list[dict],
        ttl_seconds: int,
    ) -> int:
        """Insert or refresh truck restrictions.

        Args:
            provider: Truck restriction provider name.
            restrictions: Rows keyed by ``TruckRestriction`` column names plus
                ``external_id`` and ``location`` (EWKT).
            ttl_seconds: Cache lifetime in seconds.

        Returns:
            Number of persisted rows.
        """
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=ttl_seconds)

        try:
            for row in restrictions:
                statement = select(TruckRestriction).where(
                    (TruckRestriction.provider == provider)
                    & (TruckRestriction.external_id == row["external_id"])
                )
                existing = self.session.exec(statement).first()

                if existing is not None:
                    for key, value in row.items():
                        setattr(existing, key, value)
                    existing.created_at = now
                    existing.expires_at = expires_at
                    self.session.add(existing)
                else:
                    self.session.add(
                        TruckRestriction(
                            provider=provider,
                            created_at=now,
                            expires_at=expires_at,
                            **row,
                        )
                    )

            self.session.commit()
            return len(restrictions)
        except Exception as exc:
            logger.error(
                "Error upserting truck restrictions",
                provider=provider,
                error=str(exc),
                exc_info=True,
            )
            self.session.rollback()
            raise
