"""Repository and cache table for geocoding results."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import JSON, DateTime, Text, UniqueConstraint
from sqlmodel import Column, Field, Session, SQLModel, select

from app.core.logging import get_logger
from app.providers.geo import point_to_wkt

logger = get_logger(__name__)


class GeocodingCacheEntry(SQLModel, table=True):
    """Cached geocoding result identified by provider and query hash."""

    __tablename__ = "geocoding_cache"
    __table_args__ = (
        UniqueConstraint("provider", "query_hash", name="uq_geocoding_provider_hash"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    provider: str = Field(index=True)
    query_hash: str = Field(index=True)
    query: str = Field(sa_column=Column(Text, nullable=False))
    formatted_address: str = Field(sa_column=Column(Text, nullable=False))
    location: str = Field(
        sa_column=Column(
            Geography(geometry_type="POINT", srid=4326),
            nullable=False,
        )
    )
    provider_response: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class GeocodingCacheRepository:
    """Persistence layer for geocoding cache entries."""

    def __init__(self, session: Session):
        self.session = session

    def get_valid(self, provider: str, query_hash: str) -> GeocodingCacheEntry | None:
        statement = select(GeocodingCacheEntry).where(
            (GeocodingCacheEntry.provider == provider)
            & (GeocodingCacheEntry.query_hash == query_hash)
        )
        entry = self.session.exec(statement).first()
        if entry is None:
            return None

        if entry.expires_at < datetime.now(UTC):
            logger.info(
                "Geocoding cache expired",
                provider=provider,
                query_hash=query_hash,
            )
            return None

        return entry

    def upsert(
        self,
        *,
        provider: str,
        query_hash: str,
        query: str,
        formatted_address: str,
        longitude: float,
        latitude: float,
        provider_response: dict[str, Any],
        ttl_seconds: int,
    ) -> GeocodingCacheEntry:
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=ttl_seconds)
        location = point_to_wkt(longitude, latitude)

        statement = select(GeocodingCacheEntry).where(
            (GeocodingCacheEntry.provider == provider)
            & (GeocodingCacheEntry.query_hash == query_hash)
        )
        existing = self.session.exec(statement).first()

        try:
            if existing is not None:
                existing.query = query
                existing.formatted_address = formatted_address
                existing.location = location
                existing.provider_response = provider_response
                existing.created_at = now
                existing.expires_at = expires_at
                entry = existing
            else:
                entry = GeocodingCacheEntry(
                    provider=provider,
                    query_hash=query_hash,
                    query=query,
                    formatted_address=formatted_address,
                    location=location,
                    provider_response=provider_response,
                    created_at=now,
                    expires_at=expires_at,
                )

            self.session.add(entry)
            self.session.commit()
            self.session.refresh(entry)
            return entry
        except Exception:
            self.session.rollback()
            raise
