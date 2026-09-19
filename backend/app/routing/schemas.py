"""
Routing schemas and data models.

This module defines typed request and response models for the routing API,
following the TomTom Calculate Route API v3 structure with full feature support.

Key design principles:
- coordinates are [longitude, latitude] (GeoJSON standard)
- All models use Pydantic for validation
- Optional fields for provider-specific features
- No direct TomTom dependency - these are application schemas
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# GeoJSON models are shared across all map layer domains and live in
# app.providers.geo. They are imported here so that existing
# `from app.routing.schemas import GeoJSONPoint` imports keep working.
from app.providers.geo import (  # noqa: F401
    Coordinate,
    GeoJSONLineString,
    GeoJSONMultiPoint,
    GeoJSONPoint,
)


class AvoidAreaRectangle(BaseModel):
    """Avoid area rectangle as GeoJSON Feature.

    bbox: [sw_lon, sw_lat, ne_lon, ne_lat]
    """

    type: Literal["Feature"] = "Feature"
    geometry: dict[str, Any] | None = None  # Must be null per TomTom spec
    bbox: tuple[float, float, float, float] = Field(
        description="[sw_lon, sw_lat, ne_lon, ne_lat]"
    )

    @field_validator("bbox")
    @classmethod
    def validate_bbox(
        cls, v: tuple[float, float, float, float]
    ) -> tuple[float, float, float, float]:
        """Validate bbox coordinates and order."""
        sw_lon, sw_lat, ne_lon, ne_lat = v

        # Validate ranges
        for coord_name, coord_val in [
            ("sw_lon", sw_lon),
            ("sw_lat", sw_lat),
            ("ne_lon", ne_lon),
            ("ne_lat", ne_lat),
        ]:
            if coord_name.endswith("_lon"):
                if not (-180 <= coord_val <= 180):
                    raise ValueError(f"{coord_name} must be between -180 and 180")
            else:
                if not (-90 <= coord_val <= 90):
                    raise ValueError(f"{coord_name} must be between -90 and 90")

        # Validate bbox order
        if sw_lon > ne_lon:
            raise ValueError("Southwest longitude must be <= northeast longitude")
        if sw_lat > ne_lat:
            raise ValueError("Southwest latitude must be <= northeast latitude")

        return v


class AvoidAreas(BaseModel):
    """Avoid areas configuration."""

    rectangles: list[AvoidAreaRectangle] = Field(
        max_length=10,
        default=[],
        description="Maximum 10 avoid area rectangles",
    )


# ============================================================================
# Enums and Constants
# ============================================================================


class AvoidType(StrEnum):
    """Road features to avoid."""

    TOLL_ROADS = "tollRoads"
    MOTORWAYS = "motorways"
    FERRIES = "ferries"
    UNPAVED_ROADS = "unpavedRoads"
    CARPOOLS = "carpools"
    ALREADY_USED_ROADS = "alreadyUsedRoads"
    BORDER_CROSSINGS = "borderCrossings"
    TUNNELS = "tunnels"
    CAR_TRAINS = "carTrains"


class RouteType(StrEnum):
    """Route optimization type."""

    FAST = "fast"
    SHORT = "short"
    EFFICIENT = "efficient"
    THRILLING = "thrilling"


class TravelMode(StrEnum):
    """Vehicle travel mode."""

    CAR = "car"
    TAXI = "taxi"


class TrafficMode(StrEnum):
    """Traffic mode for routing."""

    LIVE = "live"
    HISTORICAL = "historical"


class EngineType(StrEnum):
    """Vehicle engine type."""

    COMBUSTION = "combustion"
    ELECTRIC = "electric"


class ArrivalSidePreference(StrEnum):
    """Preference for which side of road to arrive on."""

    ANY_SIDE = "anySide"
    CURB_SIDE = "curbSide"


class ElectronicTollTransponder(StrEnum):
    """Electronic toll collection transponder type."""

    ALL = "all"
    NONE = "none"


# ============================================================================
# Request Models
# ============================================================================


class RouteStop(BaseModel):
    """Stop information for route legs."""

    pause_duration_in_seconds: int | None = Field(
        default=None,
        ge=0,
        description="Pause duration in seconds",
    )
    entry_points: list[GeoJSONPoint] | None = Field(
        default=None,
        description="Possible entry points for this stop",
    )
    preferred_entry_point_index: int | None = Field(
        default=None,
        description="Preferred entry point index (requires entry_points)",
    )

    @field_validator("preferred_entry_point_index")
    @classmethod
    def validate_entry_point_index(cls, v: int | None, info: Any) -> int | None:
        """Validate entry point index is within bounds."""
        if v is not None:
            entry_points = info.data.get("entry_points")
            if entry_points and (v < 0 or v >= len(entry_points)):
                raise ValueError(
                    f"preferred_entry_point_index must be 0 <= {v} < "
                    f"{len(entry_points)}"
                )
        return v


class RouteLeg(BaseModel):
    """Leg configuration for multi-leg routes."""

    route_type: RouteType | None = Field(default=None)
    route_stop: RouteStop | None = Field(default=None)
    path: GeoJSONLineString | None = Field(default=None)
    avoids: list[AvoidType] | None = Field(
        default=None,
        description="Avoid specific road types",
    )


class RoutePlanningLocations(BaseModel):
    """Route waypoints and stops."""

    origin: GeoJSONPoint = Field(description="Starting point")
    destination: GeoJSONPoint = Field(description="Destination point")
    waypoints: GeoJSONMultiPoint | None = Field(
        default=None,
        description="Intermediate waypoints",
    )


class CalculateRouteRequest(BaseModel):
    """Calculate route request.

    Comprehensive request model supporting TomTom Calculate Route API v3 features.
    """

    # Core locations
    route_planning_locations: RoutePlanningLocations

    # Path constraints
    path: GeoJSONLineString | None = Field(
        default=None,
        description="Suggested path as LineString",
    )

    # Legs for multi-leg routing
    legs: list[RouteLeg] | None = Field(
        default=None,
        description="Multi-leg route configuration",
    )

    # Avoid parameters
    avoids: list[AvoidType] | None = Field(
        default=None,
        min_length=1,
        description="Road features to avoid (non-empty list)",
    )
    avoid_areas: AvoidAreas | None = Field(
        default_factory=AvoidAreas,
        description="Areas to avoid",
    )

    # Route options
    route_type: RouteType | None = Field(
        default=None,
        description="Route optimization strategy",
    )
    traffic: TrafficMode | None = Field(
        default=None,
        description="Traffic mode: live or historical",
    )
    max_path_alternative_routes: int | None = Field(
        default=None,
        ge=0,
        le=5,
        description="Maximum number of alternative routes (0-5)",
    )
    travel_mode: TravelMode | None = Field(
        default=None,
        description="Travel mode: car or taxi",
    )
    arrival_side_preference: ArrivalSidePreference | None = Field(
        default=None,
        description="Preference for arrival side",
    )

    # Vehicle parameters
    vehicle_heading_in_degrees: int | None = Field(
        default=None,
        ge=0,
        le=359,
        description="Vehicle heading in degrees (0-359)",
    )
    vehicle_max_speed_in_kilometers_per_hour: int | None = Field(
        default=None,
        ge=0,
        le=250,
        description="Maximum speed in km/h (0-250)",
    )
    vehicle_weight_in_kilograms: int | None = Field(
        default=None,
        ge=0,
        description="Vehicle weight in kilograms",
    )
    vehicle_engine_type: EngineType | None = Field(
        default=None,
        description="Vehicle engine type",
    )
    vehicle_has_electronic_toll_collection_transponder: (
        ElectronicTollTransponder | None
    ) = Field(
        default=None,
        description="Electronic toll transponder status",
    )

    # Timing constraints
    departure_date_time: datetime | None = Field(
        default=None,
        description="Departure time (RFC3339 or 'now')",
    )
    arrival_date_time: datetime | None = Field(
        default=None,
        description="Arrival time (RFC3339)",
    )

    # API-specific options
    attributes: str | None = Field(
        default=None,
        description="Route response attributes (TomTom header)",
    )
    attributes_exclude: str | None = Field(
        default=None,
        description="Excluded route attributes",
    )
    tracking_id: str | None = Field(
        default=None,
        pattern=r"^[a-zA-Z0-9\-_.]{1,100}$",
        description="Tracking ID for request correlation",
    )
    accept_language: str | None = Field(
        default=None,
        description="Accept-Language header value",
    )

    @field_validator("avoids")
    @classmethod
    def validate_avoids_not_empty(
        cls, v: list[AvoidType] | None
    ) -> list[AvoidType] | None:
        """Ensure avoids list is not empty if provided."""
        if v is not None and len(v) == 0:
            raise ValueError("avoids list must not be empty")
        return v

    @field_validator("departure_date_time", "arrival_date_time")
    @classmethod
    def validate_timing(cls, v: datetime | None) -> datetime | None:
        """Validate timing parameters."""
        return v


# ============================================================================
# Response Models
# ============================================================================


class ProgressPoint(BaseModel):
    """Progress point along route."""

    path_index: int = Field(alias="pathIndex", description="Index in path coordinates")
    distance_in_meters: int = Field(alias="distanceInMeters")
    travel_duration_in_seconds: int = Field(alias="travelDurationInSeconds")

    class Config:
        extra = "ignore"  # Allow additional TomTom fields
        populate_by_name = True


class DeviationPoint(BaseModel):
    """Deviation point information."""

    point: GeoJSONPoint
    path_index: int = Field(alias="pathIndex")

    class Config:
        extra = "ignore"
        populate_by_name = True


class TrafficCause(BaseModel):
    """Traffic cause details."""

    main_cause_code: str | None = Field(None, alias="mainCauseCode")
    sub_cause_code: str | None = Field(None, alias="subCauseCode")

    class Config:
        extra = "ignore"
        populate_by_name = True


class Tec(BaseModel):
    """Traffic Event Code."""

    effect_code: str | None = Field(None, alias="effectCode")
    causes: list[TrafficCause] | None = None

    class Config:
        extra = "ignore"
        populate_by_name = True


class TrafficSection(BaseModel):
    """Traffic information section."""

    start_path_index: int = Field(alias="startPathIndex")
    end_path_index: int = Field(alias="endPathIndex")
    icon_category: str | None = Field(None, alias="iconCategory")
    effective_speed_in_kilometers_per_hour: int | None = Field(
        None, alias="effectiveSpeedInKilometersPerHour"
    )
    delay_duration_in_seconds: int | None = Field(None, alias="delayDurationInSeconds")
    delay_magnitude: str | None = Field(None, alias="delayMagnitude")
    tec: Tec | None = None
    event_id: int | None = Field(None, alias="eventId")

    class Config:
        extra = "ignore"
        populate_by_name = True


class SpeedRestriction(BaseModel):
    """Speed restriction in a section."""

    type: str | None = None
    in_kilometers_per_hour: int | None = Field(None, alias="inKilometersPerHour")

    class Config:
        extra = "ignore"
        populate_by_name = True


class SpeedLimitSection(BaseModel):
    """Speed limit section."""

    start_path_index: int = Field(alias="startPathIndex")
    end_path_index: int = Field(alias="endPathIndex")
    speed_restrictions: list[SpeedRestriction] | None = Field(
        None, alias="speedRestrictions"
    )

    class Config:
        extra = "ignore"
        populate_by_name = True


class CountrySection(BaseModel):
    """Country section information."""

    start_path_index: int = Field(alias="startPathIndex")
    end_path_index: int = Field(alias="endPathIndex")
    country_code_iso2: str | None = Field(None, alias="countryCodeISO2")

    class Config:
        extra = "ignore"
        populate_by_name = True


class Section(BaseModel):
    """Route section with various characteristics."""

    start_path_index: int = Field(alias="startPathIndex")
    end_path_index: int = Field(alias="endPathIndex")
    sectionType: str | None = None

    # Allow all provider-specific fields
    class Config:
        extra = "ignore"
        populate_by_name = True


class RouteSummary(BaseModel):
    """Route summary information."""

    length_in_meters: int = Field(alias="lengthInMeters")
    travel_duration_in_seconds: int = Field(alias="travelDurationInSeconds")
    traffic_delay_duration_in_seconds: int | None = Field(
        None, alias="trafficDelayDurationInSeconds"
    )
    traffic_length_in_meters: int | None = Field(None, alias="trafficLengthInMeters")
    departure_date_time: datetime | None = Field(None, alias="departureDateTime")
    arrival_date_time: datetime | None = Field(None, alias="arrivalDateTime")
    deviation_distance_in_meters: int | None = Field(
        None, alias="deviationDistanceInMeters"
    )
    deviation_duration_in_seconds: int | None = Field(
        None, alias="deviationDurationInSeconds"
    )
    deviation_point: DeviationPoint | None = Field(None, alias="deviationPoint")
    progress_points: list[ProgressPoint] | None = Field(None, alias="progressPoints")

    class Config:
        extra = "ignore"
        populate_by_name = True


class Leg(BaseModel):
    """Route leg (segment between waypoints)."""

    summary: RouteSummary
    path: GeoJSONLineString | None = None

    class Config:
        extra = "ignore"
        populate_by_name = True


class Route(BaseModel):
    """Single calculated route."""

    summary: RouteSummary
    legs: list[Leg] | None = None
    sections: list[Section] | None = None
    guidance: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def convert_sections_dict_to_list(cls, data: Any) -> Any:
        """Convert sections dict format to list format if needed.

        TomTom API may return sections as a dict like:
        {
            "country": [{...}, {...}],
            "traffic": [{...}],
            "speedLimits": [{...}]
        }

        This validator converts it to a flat list of Section objects.
        """
        if isinstance(data, dict) and "sections" in data:
            sections = data["sections"]
            # If sections is a dict, flatten it to a list
            if isinstance(sections, dict):
                flattened_sections = []
                for section_type, section_list in sections.items():
                    if isinstance(section_list, list):
                        for section in section_list:
                            # Add sectionType if not present
                            if (
                                isinstance(section, dict)
                                and "sectionType" not in section
                            ):
                                section["sectionType"] = section_type
                            flattened_sections.append(section)
                data["sections"] = flattened_sections
        return data

    class Config:
        extra = "ignore"
        populate_by_name = True


class CalculateRouteResponse(BaseModel):
    """Calculate route response.

    Contains one or more routes depending on maxPathAlternativeRoutes parameter.
    """

    routes: list[Route]
    format_version: str | None = Field(None, alias="formatVersion")

    class Config:
        extra = "ignore"
        populate_by_name = True
