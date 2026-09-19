"""
Provider domain schemas.

DTOs exchanged between map layer services and their providers.
Routing schemas live in :mod:`app.routing.schemas` for historical reasons.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.providers.geo import Coordinate, GeoJSONLineString, GeoJSONPoint

# ============================================================================
# Common query
# ============================================================================


class LayerQuery(BaseModel):
    """Query describing the corridor along which layer data is requested."""

    path: GeoJSONLineString = Field(description="Route geometry to search along")
    radius_meters: int = Field(
        default=5000,
        ge=1,
        le=100_000,
        description="Search radius around the route corridor",
    )
    limit: int = Field(
        default=200,
        ge=1,
        le=1000,
        description="Maximum number of features to return",
    )

    @property
    def coordinates(self) -> list[Coordinate]:
        """Route coordinates as a plain list."""
        return self.path.coordinates


# ============================================================================
# Traffic
# ============================================================================


class TrafficSeverity(StrEnum):
    """Normalized traffic incident severity."""

    UNKNOWN = "unknown"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    SEVERE = "severe"


class TrafficIncident(BaseModel):
    """Single traffic incident along the route."""

    external_id: str | None = Field(default=None, description="Provider incident id")
    severity: TrafficSeverity = TrafficSeverity.UNKNOWN
    category: str | None = Field(default=None, description="Incident category")
    description: str | None = None
    location: GeoJSONPoint | None = None
    delay_seconds: int | None = Field(default=None, ge=0)
    length_meters: int | None = Field(default=None, ge=0)
    start_time: datetime | None = None
    end_time: datetime | None = None


class TrafficLayerData(BaseModel):
    """Traffic layer payload."""

    provider: str
    incidents: list[TrafficIncident] = Field(default_factory=list)
    total_delay_seconds: int = Field(default=0, ge=0)
    observed_at: datetime | None = None
    raw: dict[str, Any] | None = Field(
        default=None, description="Provider payload for debugging"
    )


# ============================================================================
# Fuel
# ============================================================================


class FuelStationData(BaseModel):
    """Fuel station along the route."""

    external_id: str = Field(description="Stable provider identifier")
    name: str
    brand: str | None = None
    address: str | None = None
    location: GeoJSONPoint
    diesel_price: float | None = Field(default=None, ge=0)
    truck_accessible: bool = True
    raw: dict[str, Any] | None = None


# ============================================================================
# Truck restrictions
# ============================================================================


class RestrictionType(StrEnum):
    """Normalized truck restriction type."""

    BRIDGE_HEIGHT = "bridge_height"
    WEIGHT_LIMIT = "weight_limit"
    WIDTH_LIMIT = "width_limit"
    LENGTH_LIMIT = "length_limit"
    HAZMAT = "hazmat"
    NO_TRUCKS = "no_trucks"
    OTHER = "other"


class TruckRestrictionData(BaseModel):
    """Truck restriction along the route."""

    external_id: str = Field(description="Stable provider identifier")
    restriction_type: RestrictionType = RestrictionType.OTHER
    description: str | None = None
    location: GeoJSONPoint
    max_height_cm: int | None = Field(default=None, ge=0)
    max_weight_kg: int | None = Field(default=None, ge=0)
    max_width_cm: int | None = Field(default=None, ge=0)
    max_length_cm: int | None = Field(default=None, ge=0)
    raw: dict[str, Any] | None = None
