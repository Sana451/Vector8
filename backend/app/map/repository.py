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
from app.map.models import (
    FuelStation,
    MapRestAreasCache,
    TrafficSnapshot,
    TruckRestriction,
)
from app.providers.geo import Coordinate, linestring_to_wkt, point_to_wkt

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
            # Build map of external_ids to stations for fast lookup
            stations_by_id = {row["external_id"]: row for row in stations}
            external_ids = list(stations_by_id.keys())

            # Fetch existing stations with matching external IDs
            existing_map: dict[str, FuelStation] = {}
            for external_id in external_ids:
                statement = select(FuelStation).where(
                    (FuelStation.provider == provider)
                    & (FuelStation.external_id == external_id)
                )
                existing = self.session.exec(statement).first()
                if existing is not None:
                    existing_map[external_id] = existing

            # Process all stations
            for external_id, row in stations_by_id.items():
                existing = existing_map.get(external_id)

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


class RestAreaCacheRepository:
    """Repository for route-specific HERE rest area cache rows."""

    def __init__(self, session: Session):
        self.session = session

    def get_valid(self, provider: str, request_hash: str) -> list[MapRestAreasCache]:
        statement = (
            select(MapRestAreasCache)
            .where(MapRestAreasCache.provider == provider)
            .where(MapRestAreasCache.request_hash == request_hash)
            .where(MapRestAreasCache.expires_at >= datetime.now(UTC))
        )
        return list(self.session.exec(statement).all())

    def replace_many(
        self,
        *,
        provider: str,
        request_hash: str,
        route_hash: str,
        categories_hash: str,
        corridor_width_meters: int,
        rows: list[dict],
        ttl_seconds: int,
    ) -> int:
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=ttl_seconds)

        try:
            existing_statement = select(MapRestAreasCache).where(
                (MapRestAreasCache.provider == provider)
                & (MapRestAreasCache.request_hash == request_hash)
            )
            existing_rows = {
                row.provider_place_id: row
                for row in self.session.exec(existing_statement).all()
            }
            seen_place_ids: set[str] = set()

            for row in rows:
                provider_place_id = row["provider_place_id"]
                seen_place_ids.add(provider_place_id)
                existing = existing_rows.get(provider_place_id)

                if existing is not None:
                    for key, value in row.items():
                        setattr(existing, key, value)
                    existing.route_hash = route_hash
                    existing.categories_hash = categories_hash
                    existing.corridor_width_meters = corridor_width_meters
                    existing.fetched_at = now
                    existing.expires_at = expires_at
                    self.session.add(existing)
                    continue

                self.session.add(
                    MapRestAreasCache(
                        provider=provider,
                        request_hash=request_hash,
                        route_hash=route_hash,
                        categories_hash=categories_hash,
                        corridor_width_meters=corridor_width_meters,
                        fetched_at=now,
                        expires_at=expires_at,
                        **row,
                    )
                )

            for provider_place_id, existing in existing_rows.items():
                if provider_place_id not in seen_place_ids:
                    self.session.delete(existing)

            self.session.commit()
            return len(rows)
        except Exception as exc:
            logger.error(
                "Error replacing rest area cache rows",
                provider=provider,
                request_hash=request_hash,
                error=str(exc),
                exc_info=True,
            )
            self.session.rollback()
            raise


def build_rest_area_row(
    *,
    provider_place_id: str,
    title: str,
    longitude: float,
    latitude: float,
    payload: dict,
    access: list[dict],
    address: dict | None,
    categories: list[dict],
    distance_meters: float | None,
    result_type: str | None,
    ontology_id: str | None,
    opening_hours: list[dict],
    contacts: list[dict],
    chains: list[dict],
    references: list[dict],
    metadata_payload: dict | None,
) -> dict:
    """Build repository row values for a cached rest area."""
    return {
        "provider_place_id": provider_place_id,
        "title": title,
        "position": point_to_wkt(longitude, latitude),
        "access": access,
        "address": address,
        "categories": categories,
        "distance_meters": distance_meters,
        "result_type": result_type,
        "ontology_id": ontology_id,
        "opening_hours": opening_hours,
        "contacts": contacts,
        "chains": chains,
        "references": references,
        "metadata_payload": metadata_payload,
        "payload": payload,
    }
