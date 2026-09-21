"""
Map layer persistence models.

Cache tables for map layers backed by external providers. Each table keeps its
own ``expires_at`` so that TTLs can differ per domain (traffic is volatile,
truck restrictions are near-static).

Invalidation is lazy: expired rows are ignored on read and overwritten on the
next successful provider call.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import JSON, DateTime, UniqueConstraint
from sqlmodel import Column, Field, SQLModel


def get_datetime_utc() -> datetime:
    """Get current datetime in UTC with timezone awareness."""
    return datetime.now(UTC)


class TrafficSnapshot(SQLModel, table=True):
    """Cached traffic layer payload for a route corridor.

    Identified uniquely by the ``(provider, request_hash)`` pair, where the hash
    covers the route geometry and search radius.
    """

    __tablename__ = "traffic_snapshots"
    __table_args__ = (
        UniqueConstraint("provider", "request_hash", name="uq_traffic_provider_hash"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    provider: str = Field(index=True)
    request_hash: str = Field(index=True)
    geometry: str | None = Field(
        default=None,
        sa_column=Column(
            Geography(geometry_type="LINESTRING", srid=4326),
            nullable=True,
        ),
    )
    payload: dict[str, Any] = Field(sa_column=Column(JSON))
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class FuelStation(SQLModel, table=True):
    """Fuel station known to the platform.

    Rows are upserted from the configured fuel provider and queried spatially
    with ``ST_DWithin`` against the route geometry.
    """

    __tablename__ = "fuel_stations"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_fuel_provider_external"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    provider: str = Field(index=True)
    external_id: str = Field(index=True, max_length=255)
    name: str = Field(max_length=255)
    brand: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=512)
    location: str = Field(
        sa_column=Column(
            Geography(geometry_type="POINT", srid=4326),
            nullable=False,
        )
    )
    diesel_price: float | None = Field(default=None)
    truck_accessible: bool = Field(default=True)
    payload: dict[str, Any] = Field(sa_column=Column(JSON))
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class TruckRestriction(SQLModel, table=True):
    """Truck restriction (bridge clearance, weight limit, etc.).

    Rows are upserted from the configured truck restriction provider and
    queried spatially with ``ST_DWithin`` against the route geometry.
    """

    __tablename__ = "truck_restrictions"
    __table_args__ = (
        UniqueConstraint(
            "provider", "external_id", name="uq_truck_restriction_provider_external"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    provider: str = Field(index=True)
    external_id: str = Field(index=True, max_length=255)
    restriction_type: str = Field(max_length=64)
    description: str | None = Field(default=None, max_length=512)
    location: str = Field(
        sa_column=Column(
            Geography(geometry_type="POINT", srid=4326),
            nullable=False,
        )
    )
    max_height_cm: int | None = Field(default=None)
    max_weight_kg: int | None = Field(default=None)
    max_width_cm: int | None = Field(default=None)
    max_length_cm: int | None = Field(default=None)
    payload: dict[str, Any] = Field(sa_column=Column(JSON))
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class MapRestAreasCache(SQLModel, table=True):
    """Route-specific cache rows for HERE rest areas."""

    __tablename__ = "map_rest_areas_cache"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "request_hash",
            "provider_place_id",
            name="uq_map_rest_areas_provider_request_place",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    provider: str = Field(index=True)
    request_hash: str = Field(index=True)
    route_hash: str = Field(index=True)
    categories_hash: str = Field(index=True)
    corridor_width_meters: int
    provider_place_id: str = Field(index=True, max_length=255)
    title: str = Field(max_length=255)
    position: str = Field(
        sa_column=Column(
            Geography(geometry_type="POINT", srid=4326),
            nullable=False,
        )
    )
    access: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    address: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    categories: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON)
    )
    distance_meters: float | None = Field(default=None)
    result_type: str | None = Field(default=None, max_length=64)
    ontology_id: str | None = Field(default=None, max_length=255)
    opening_hours: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )
    contacts: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    chains: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    references: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON)
    )
    metadata_payload: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column("metadata", JSON),
    )
    payload: dict[str, Any] = Field(sa_column=Column(JSON))
    fetched_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
