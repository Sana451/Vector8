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


class FuelOptimizationEconomicsInput(BaseModel):
    """Costs of a refuelling stop beyond the fuel price itself.

    Money is expressed in the same currency as the diesel price (USD).
    Omitted fields fall back to the server defaults (``FUEL_OPT_*`` settings),
    which are zero unless configured.

    With everything at zero the optimizer still prices the fuel burnt on the
    detour, but ignores how long the stop takes.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "downtime_cost_per_hour": "75",
                "dwell_minutes": "30",
                "fixed_stop_cost": "0",
            }
        }
    )

    downtime_cost_per_hour: Decimal | None = Field(
        default=None,
        ge=0,
        description=(
            "Cost of one hour the whole truck spends standing still, in currency "
            "units per hour. This is a single lump figure, not just the driver's "
            "wage: include driver pay with taxes and benefits, vehicle holding "
            "cost (lease or depreciation, insurance, permits) and, if you use "
            "it, the revenue lost per hour. Count each item once. Fuel is "
            "excluded. Set to 0 to ignore stop duration entirely."
        ),
    )
    dwell_minutes: Decimal | None = Field(
        default=None,
        ge=0,
        description=(
            "Minutes spent leaving the route, fuelling and getting back on it. "
            "Priced through downtime_cost_per_hour, so it has no effect while "
            "that value is 0."
        ),
    )
    fixed_stop_cost: Decimal | None = Field(
        default=None,
        ge=0,
        description=(
            "Flat charge per stop in currency units (parking, service fees). "
            "Excludes the cost of time, which is already covered by "
            "downtime_cost_per_hour."
        ),
    )


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
    economics: FuelOptimizationEconomicsInput | None = None
    include_debug: bool = False


class FuelOptimizationAlternativePublic(BaseModel):
    """A station weighed against the chosen one and not picked."""

    station_id: uuid.UUID
    name: str
    latitude: Decimal
    longitude: Decimal
    route_offset_meters: Decimal
    fuel_price_per_gallon: Decimal
    detour_distance_meters: Decimal
    detour_time_seconds: int
    cheaper_by_sticker: bool
    outcome: Literal[
        "higher_effective_price",
        "tie_broken_by_distance",
        "no_fuel_to_buy",
        "not_reachable",
        "overhead_exceeds_savings",
    ]
    effective_price_per_gallon: Decimal | None = None
    delta_vs_chosen_per_gallon: Decimal | None = Field(
        default=None,
        description="Effective price minus the chosen one's; positive means worse.",
    )
    estimated_savings: Decimal | None = None
    stop_overhead_cost: Decimal | None = None


class FuelOptimizationSelectionPublic(BaseModel):
    """Why the optimizer drove to this station, with the numbers it used."""

    rule: Literal["lowest_effective_price", "cheaper_ahead_pays_off"]
    sticker_price_per_gallon: Decimal
    detour_fuel_gallons: Decimal
    detour_fuel_cost: Decimal
    time_cost: Decimal
    fixed_stop_cost: Decimal
    effective_price_per_gallon: Decimal | None = None
    premium_per_gallon: Decimal | None = None
    volume_gallons: Decimal | None = None
    delivered_gallons: Decimal | None = None
    estimated_savings: Decimal | None = None
    stop_overhead_cost: Decimal | None = None
    shifted_volume_gallons: Decimal | None = None
    alternatives: list[FuelOptimizationAlternativePublic] = Field(default_factory=list)
    alternatives_omitted_count: int = 0


class FuelOptimizationLookaheadPublic(BaseModel):
    """What was decided at a stop about a cheaper station further ahead."""

    rule: Literal[
        "cheaper_ahead_pays_off", "cheaper_ahead_rejected", "no_cheaper_ahead"
    ]
    station_id: uuid.UUID | None = None
    station_name: str | None = None
    price_difference_per_gallon: Decimal | None = None
    estimated_savings: Decimal | None = None
    stop_overhead_cost: Decimal | None = None
    shifted_volume_gallons: Decimal | None = None


class FuelOptimizationEconomicsPublic(BaseModel):
    """Stop-cost assumptions the plan was computed with (USD)."""

    downtime_cost_per_hour: Decimal
    dwell_minutes: Decimal
    fixed_stop_cost: Decimal


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
    selection: FuelOptimizationSelectionPublic | None = None
    lookahead: FuelOptimizationLookaheadPublic | None = None


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
    selection: FuelOptimizationSelectionPublic | None = None
    lookahead: FuelOptimizationLookaheadPublic | None = None
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
    economics: FuelOptimizationEconomicsPublic | None = None
    debug: dict[str, Any] | None = None
