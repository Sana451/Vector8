"""Request and response schemas for trip plans."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.providers.geo import Coordinate, GeoJSONLineString
from app.trip_plans.domain import TripPlanStatus

MAX_TRIP_PLAN_NAME_LENGTH = 255
MAX_STOP_DURATION_MINUTES = 24 * 60


class TripPlanStationDetails(BaseModel):
    """Live station facts shown alongside a stop, mirroring the /map popup."""

    name: str
    brand: str | None = None
    address: str | None = None
    fuel_type: str | None = None
    diesel_price: float | None = None
    currency: str | None = None
    has_adblue: bool = False
    is_open: bool | None = None
    medium_truck_accessible: bool | None = None
    large_truck_accessible: bool | None = None
    phone: str | None = None
    website: str | None = None


class TripPlanStopSnapshot(BaseModel):
    """A fuel stop frozen at the moment the trip plan was created.

    Kept denormalized so the driver view stays stable even if the optimization
    run is recalculated later. ``station`` is filled in at read time only.
    """

    sequence: int
    kind: Literal["start", "station", "refuel", "destination"]
    label: str
    station_id: uuid.UUID | None = None
    coordinate: Coordinate = Field(description="[longitude, latitude] in WGS84")
    route_offset_meters: Decimal | None = None
    fuel_before_gallons: Decimal | None = None
    fuel_added_gallons: Decimal | None = None
    fuel_after_gallons: Decimal | None = None
    fuel_price_per_gallon: Decimal | None = None
    fuel_cost: Decimal | None = None
    detour_distance_meters: Decimal | None = None
    detour_time_seconds: int | None = None
    station: TripPlanStationDetails | None = None


class TripPlanCreateRequest(BaseModel):
    optimization_run_id: uuid.UUID
    name: str | None = Field(default=None, max_length=MAX_TRIP_PLAN_NAME_LENGTH)
    provider: str | None = None
    stop_duration_minutes: int | None = Field(
        default=None, ge=0, le=MAX_STOP_DURATION_MINUTES
    )


class TripPlanRefineRequest(BaseModel):
    provider: str | None = None
    stop_duration_minutes: int | None = Field(
        default=None, ge=0, le=MAX_STOP_DURATION_MINUTES
    )
    force_refresh: bool = False


class TripPlanAssignRequest(BaseModel):
    driver_id: uuid.UUID | None = None


class TripPlanStatusUpdateRequest(BaseModel):
    status: TripPlanStatus


class TripPlanShareRequest(BaseModel):
    """Issue a public link, or revoke the current one with ``enabled=False``."""

    enabled: bool = True


class TripPlanSharePublic(BaseModel):
    share_token: str | None = None


class TripPlanDeltaPublic(BaseModel):
    """Difference between the base route and the refined one."""

    distance_meters: int
    duration_seconds: int


class TripPlanPublic(BaseModel):
    """List representation: no geometry, no stops."""

    id: uuid.UUID
    name: str
    status: TripPlanStatus
    owner_id: uuid.UUID
    assigned_driver_id: uuid.UUID | None = None
    assigned_at: datetime | None = None
    vehicle_id: uuid.UUID
    vehicle_name: str | None = None
    vehicle_unit_number: str | None = None
    base_route_id: uuid.UUID
    optimization_run_id: uuid.UUID
    refined_route_id: uuid.UUID | None = None
    refined_provider: str | None = None
    base_distance_meters: int
    base_duration_seconds: int
    refined_distance_meters: int | None = None
    refined_duration_seconds: int | None = None
    origin_label: str | None = None
    destination_label: str | None = None
    refine_error: str | None = None
    number_of_stops: int
    is_shared: bool = False
    created_at: datetime
    updated_at: datetime


class TripPlanDetailPublic(TripPlanPublic):
    """Detail representation: adds geometry, stops and deltas."""

    stops: list[TripPlanStopSnapshot] = Field(default_factory=list)
    base_geometry: GeoJSONLineString | None = None
    refined_geometry: GeoJSONLineString | None = None
    delta: TripPlanDeltaPublic | None = None
    usable_tank_gallons: Decimal | None = None


class TripPlansPublic(BaseModel):
    data: list[TripPlanPublic]
    count: int


class TripPlanSharedPublic(BaseModel):
    """Read-only view behind a share token.

    Deliberately omits every identifier that could be used to reach the rest of
    the API: whoever holds the link has no account and must only see the route
    itself, not who planned it.
    """

    name: str
    status: TripPlanStatus
    distance_meters: int
    duration_seconds: int
    number_of_stops: int
    created_at: datetime
    stops: list[TripPlanStopSnapshot] = Field(default_factory=list)
    geometry: GeoJSONLineString | None = None
