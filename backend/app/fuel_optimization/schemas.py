from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.fuel_optimization.domain import (
    FuelOptimizationAlgorithm,
    FuelOptimizationFailureReason,
    FuelOptimizationStatus,
)


class FuelOptimizationConstraintsInput(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reserve_gallons": "20",
                "min_refuel_gallons": "10",
                "max_refuel_gallons": "100",
                "max_allowed_detour_meters": "100000",
            }
        }
    )

    reserve_gallons: Decimal | None = Field(default=None, ge=0)
    min_refuel_gallons: Decimal | None = Field(default=None, ge=0)
    max_refuel_gallons: Decimal | None = Field(default=None, gt=0)
    max_allowed_detour_meters: Decimal | None = Field(default=None, ge=0)


class FuelOptimizationCalculateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "route_id": "11111111-1111-1111-1111-111111111111",
                    "vehicle_id": "22222222-2222-2222-2222-222222222222",
                    "algorithm": "greedy",
                    "initial_fuel_gallons": "60",
                    "constraints": {
                        "max_allowed_detour_meters": "100000",
                    },
                    "include_debug": False,
                }
            ]
        }
    )

    route_id: uuid.UUID
    vehicle_id: uuid.UUID
    algorithm: FuelOptimizationAlgorithm = FuelOptimizationAlgorithm.GREEDY
    initial_fuel_gallons: Decimal = Field(ge=0)
    constraints: FuelOptimizationConstraintsInput | None = None
    include_debug: bool = False


class FuelOptimizationStopPublic(BaseModel):
    sequence: int
    station_id: uuid.UUID
    route_offset_meters: Decimal
    fuel_before_gallons: Decimal
    fuel_added_gallons: Decimal
    fuel_after_gallons: Decimal
    fuel_price_per_gallon: Decimal
    fuel_cost: Decimal
    detour_distance_meters: Decimal
    detour_time_seconds: int


class FuelOptimizationFailureTargetPublic(BaseModel):
    kind: Literal["start", "station", "destination"]
    station_id: uuid.UUID | None = None
    name: str
    route_offset_meters: Decimal
    coordinate: tuple[Decimal, Decimal]
    fuel_required_gallons: Decimal
    available_fuel_gallons: Decimal
    reserve_gallons: Decimal
    projected_arrival_fuel_gallons: Decimal
    deficit_gallons: Decimal


class FuelOptimizationFailurePublic(BaseModel):
    reason: FuelOptimizationFailureReason
    message: str
    stopped_at_route_offset_meters: Decimal
    last_reachable_station_id: uuid.UUID | None = None
    last_reachable_route_offset_meters: Decimal
    available_fuel_gallons: Decimal
    reserve_gallons: Decimal
    primary_target: FuelOptimizationFailureTargetPublic
    unreachable_stations: list[FuelOptimizationFailureTargetPublic] = Field(
        default_factory=list
    )
    destination: FuelOptimizationFailureTargetPublic | None = None


class FuelOptimizationItineraryPointPublic(BaseModel):
    sequence: int
    kind: Literal["start", "station", "refuel", "destination", "unreachable_station"]
    status: Literal["reached", "unreachable"]
    label: str
    station_id: uuid.UUID | None = None
    route_offset_meters: Decimal
    coordinate: tuple[Decimal, Decimal]
    fuel_gallons: Decimal | None = None
    fuel_before_gallons: Decimal | None = None
    fuel_added_gallons: Decimal | None = None
    fuel_after_gallons: Decimal | None = None
    fuel_price_per_gallon: Decimal | None = None
    fuel_cost: Decimal | None = None
    detour_distance_meters: Decimal | None = None
    detour_time_seconds: int | None = None
    fuel_required_gallons: Decimal | None = None
    available_fuel_gallons: Decimal | None = None
    reserve_gallons: Decimal | None = None
    deficit_gallons: Decimal | None = None
    is_primary_failure_target: bool = False
    is_failure_point: bool = False


class FuelOptimizationSummaryPublic(BaseModel):
    total_fuel_consumed_gallons: Decimal
    total_fuel_purchased_gallons: Decimal
    total_fuel_cost: Decimal
    total_detour_distance_meters: Decimal
    total_detour_time_seconds: int
    number_of_stops: int
    remaining_fuel_gallons: Decimal


class FuelOptimizationSkippedStationPointPublic(BaseModel):
    station_id: uuid.UUID
    name: str
    latitude: Decimal
    longitude: Decimal
    route_offset_meters: Decimal


class FuelOptimizationSkippedStationStatPublic(BaseModel):
    reason: str
    description: str
    count: int
    sample_points: list[FuelOptimizationSkippedStationPointPublic] = Field(
        default_factory=list
    )
    omitted_points_count: int = 0


class FuelOptimizationExplanationPublic(BaseModel):
    summary: str
    outcome: str
    key_points: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    skipped_station_stats: list[FuelOptimizationSkippedStationStatPublic] = Field(
        default_factory=list
    )


class FuelOptimizationCalculateResponse(BaseModel):
    route_id: uuid.UUID
    vehicle_id: uuid.UUID
    optimization_run_id: uuid.UUID
    status: FuelOptimizationStatus
    algorithm: FuelOptimizationAlgorithm
    algorithm_version: str
    summary: FuelOptimizationSummaryPublic
    stops: list[FuelOptimizationStopPublic]
    itinerary: list[FuelOptimizationItineraryPointPublic]
    failure: FuelOptimizationFailurePublic | None
    explanation: FuelOptimizationExplanationPublic
    debug: dict[str, Any] | None = None
