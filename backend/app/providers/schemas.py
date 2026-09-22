"""
Provider domain schemas.

DTOs exchanged between map layer services and their providers.
Routing schemas live in :mod:`app.routing.schemas` for historical reasons.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import settings
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
        le=settings.MAP_LAYER_RESULT_LIMIT,
        description="Maximum number of features to return",
    )

    @property
    def coordinates(self) -> list[Coordinate]:
        """Route coordinates as a plain list."""
        return self.path.coordinates


class RestAreaQuery(BaseModel):
    """Query for HERE rest areas searched along a route."""

    path: GeoJSONLineString = Field(
        description="Original route geometry to search along"
    )
    categories: list[str] = Field(
        min_length=1,
        description="Confirmed HERE category ids to search for",
    )
    corridor_width_meters: int = Field(
        default=1000,
        ge=1,
        le=50_000,
        description="Maximum distance from the route centerline in meters",
    )
    limit: int = Field(
        default=200,
        ge=1,
        le=1000,
        description="Maximum number of features to return",
    )
    ranking: str | None = Field(
        default=None,
        description="Optional HERE ranking mode, e.g. excursionDistance",
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
    currency: str | None = None
    fuel_type: str | None = None
    distance_meters: float | None = Field(default=None, ge=0)
    is_open: bool | None = None
    opening_hours: list[dict[str, Any]] = Field(default_factory=list)
    phone: str | None = None
    website: str | None = None
    has_adblue: bool = False
    medium_truck_accessible: bool = True
    large_truck_accessible: bool = True
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


# ============================================================================
# Rest areas / HERE POI
# ============================================================================


class RestAreaCategory(BaseModel):
    """Single HERE category assigned to a POI."""

    id: str
    name: str | None = None
    primary: bool | None = None


class RestAreaAddress(BaseModel):
    """Normalized subset of the HERE address payload."""

    label: str | None = None
    country_code: str | None = None
    state: str | None = None
    county: str | None = None
    city: str | None = None
    district: str | None = None
    street: str | None = None
    house_number: str | None = None
    postal_code: str | None = None


class RestAreaChain(BaseModel):
    """Chain affiliation returned by HERE."""

    id: str | None = None
    name: str | None = None


class RestAreaReferenceSupplier(BaseModel):
    """Supplier metadata nested under a HERE reference."""

    id: str | None = None
    name: str | None = None


class RestAreaReference(BaseModel):
    """External supplier reference returned by HERE."""

    id: str | None = None
    supplier: RestAreaReferenceSupplier | None = None


class RestAreaData(BaseModel):
    """Normalized rest area / truck POI returned by HERE."""

    provider: str
    provider_place_id: str
    title: str
    result_type: str | None = None
    position: GeoJSONPoint
    access_points: list[GeoJSONPoint] = Field(default_factory=list)
    address: RestAreaAddress | None = None
    categories: list[RestAreaCategory] = Field(default_factory=list)
    distance_meters: float | None = Field(default=None, ge=0)
    ontology_id: str | None = None
    chains: list[RestAreaChain] = Field(default_factory=list)
    references: list[RestAreaReference] = Field(default_factory=list)
    contacts: list[dict[str, Any]] = Field(default_factory=list)
    opening_hours: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] | None = None
