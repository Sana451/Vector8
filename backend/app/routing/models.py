"""
Routing domain models.

Persistence and domain entities for route calculations.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import JSON, DateTime
from sqlmodel import Column, Field, SQLModel


def get_datetime_utc() -> datetime:
    """Get current datetime in UTC with timezone awareness."""
    return datetime.now(UTC)


class RouteCalculation(SQLModel, table=True):
    """Persisted routing calculation result.

    Represents a calculated route from a routing provider (e.g., TomTom).
    Identified uniquely by (provider, request_hash) pair.

    Attributes:
        id: Unique identifier (UUID).
        provider: Routing provider name (e.g., 'tomtom').
        request_hash: SHA-256 hash of routing request parameters.
        origin: Origin point as PostGIS POINT in WGS84.
        destination: Destination point as PostGIS POINT in WGS84.
        geometry: Route geometry as PostGIS LINESTRING in WGS84, nullable.
        distance_meters: Route distance in meters (normalized from provider).
        duration_seconds: Route duration in seconds (normalized from provider).
        request_data: Full CalculateRouteRequest serialized as JSON.
        provider_response: Full provider API response as JSON.
        created_at: When record was created (UTC).
        expires_at: When cached result expires (UTC).
    """

    __tablename__ = "route_calculations"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    provider: str = Field(index=True)
    request_hash: str = Field(index=True)
    origin: str = Field(
        sa_column=Column(
            Geography(geometry_type="POINT", srid=4326),
            nullable=False,
        )
    )
    destination: str = Field(
        sa_column=Column(
            Geography(geometry_type="POINT", srid=4326),
            nullable=False,
        )
    )
    geometry: str | None = Field(
        default=None,
        sa_column=Column(
            Geography(geometry_type="LINESTRING", srid=4326),
            nullable=True,
        ),
    )
    distance_meters: int
    duration_seconds: int
    request_data: dict[str, Any] = Field(sa_column=Column(JSON))
    provider_response: dict[str, Any] = Field(sa_column=Column(JSON))
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    class Config:
        """SQLModel config."""

        json_schema_extra = {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "provider": "tomtom",
                    "request_hash": "abc123...",
                    "origin": "SRID=4326;POINT(-74.0060 40.7128)",
                    "destination": "SRID=4326;POINT(-71.0589 42.3601)",
                    "geometry": "SRID=4326;LINESTRING(...)",
                    "distance_meters": 367000,
                    "duration_seconds": 21600,
                    "request_data": {...},
                    "provider_response": {...},
                    "created_at": "2026-09-18T10:30:00Z",
                    "expires_at": "2026-09-18T14:30:00Z",
                }
            ]
        }
