from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

MONEY_QUANT = Decimal("0.01")
FUEL_QUANT = Decimal("0.0001")
DISTANCE_QUANT = Decimal("0.01")
ZERO = Decimal("0")
MILES_PER_METER = Decimal("0.000621371192237334")


class FuelOptimizationAlgorithm(StrEnum):
    GREEDY = "greedy"


class FuelOptimizationStatus(StrEnum):
    SUCCESS = "success"
    INFEASIBLE = "infeasible"


class UnsupportedOptimizationAlgorithmError(Exception):
    pass


class InvalidFuelOptimizationInputError(Exception):
    pass


@dataclass(frozen=True)
class VehicleFuelProfile:
    id: UUID
    fuel_type: str
    tank_capacity_gallons: Decimal
    usable_tank_capacity_gallons: Decimal
    consumption_mpg: Decimal
    reserve_gallons: Decimal
    min_refuel_gallons: Decimal | None = None
    max_refuel_gallons: Decimal | None = None

    def __post_init__(self) -> None:
        if self.tank_capacity_gallons <= ZERO:
            raise InvalidFuelOptimizationInputError(
                "tank_capacity_gallons must be greater than 0"
            )
        if self.usable_tank_capacity_gallons <= ZERO:
            raise InvalidFuelOptimizationInputError(
                "usable_tank_capacity_gallons must be greater than 0"
            )
        if self.usable_tank_capacity_gallons > self.tank_capacity_gallons:
            raise InvalidFuelOptimizationInputError(
                "usable_tank_capacity_gallons must be less than or equal to tank_capacity_gallons"
            )
        if self.consumption_mpg <= ZERO:
            raise InvalidFuelOptimizationInputError(
                "consumption_mpg must be greater than 0"
            )
        if self.reserve_gallons < ZERO:
            raise InvalidFuelOptimizationInputError(
                "reserve_gallons must be greater than or equal to 0"
            )
        if self.reserve_gallons >= self.usable_tank_capacity_gallons:
            raise InvalidFuelOptimizationInputError(
                "reserve_gallons must be less than usable_tank_capacity_gallons"
            )


@dataclass(frozen=True)
class Vehicle:
    id: UUID
    name: str
    unit_number: str
    vehicle_type: str
    fuel_profile: VehicleFuelProfile
    routing_profile_id: UUID | None = None


@dataclass(frozen=True)
class Route:
    id: UUID
    total_distance_meters: Decimal
    duration_seconds: int
    geometry_coordinates: list[tuple[float, float]]


@dataclass(frozen=True)
class Detour:
    distance_meters: Decimal
    time_seconds: int
    is_approximation: bool = True


@dataclass(frozen=True)
class FuelStationCandidate:
    station_id: UUID
    route_offset_meters: Decimal
    distance_from_route_meters: Decimal
    excursion_distance_meters: Decimal
    latitude: Decimal
    longitude: Decimal
    fuel_type: str
    fuel_price_per_gallon: Decimal
    truck_accessible: bool
    detour: Detour


@dataclass(frozen=True)
class FuelOptimizationConstraints:
    reserve_gallons: Decimal
    max_allowed_detour_meters: Decimal | None = None


@dataclass(frozen=True)
class FuelOptimizationRequest:
    route_id: UUID
    vehicle_id: UUID
    initial_fuel_gallons: Decimal
    algorithm: FuelOptimizationAlgorithm = FuelOptimizationAlgorithm.GREEDY
    constraints: FuelOptimizationConstraints | None = None


class FuelConsumptionModel(Protocol):
    def fuel_required(self, distance_miles: Decimal, vehicle: Vehicle) -> Decimal: ...


class DetourCalculator(Protocol):
    def calculate(self, distance_from_route_meters: Decimal) -> Detour: ...


class FuelOptimizationStrategy(Protocol):
    def optimize(self, context: FuelOptimizationContext) -> FuelOptimizationPlan: ...


@dataclass(frozen=True)
class FuelOptimizationStop:
    sequence: int
    station_id: UUID
    route_offset_meters: Decimal
    fuel_before_gallons: Decimal
    fuel_added_gallons: Decimal
    fuel_after_gallons: Decimal
    fuel_price_per_gallon: Decimal
    fuel_cost: Decimal
    detour_distance_meters: Decimal
    detour_time_seconds: int


@dataclass(frozen=True)
class FuelOptimizationPlan:
    algorithm: FuelOptimizationAlgorithm
    algorithm_version: str
    vehicle_id: UUID
    route_id: UUID
    status: FuelOptimizationStatus
    stops: list[FuelOptimizationStop] = field(default_factory=list)
    total_fuel_consumed_gallons: Decimal = ZERO
    total_fuel_purchased_gallons: Decimal = ZERO
    total_fuel_cost: Decimal = ZERO
    total_detour_distance_meters: Decimal = ZERO
    total_detour_time_seconds: int = 0
    number_of_stops: int = 0
    remaining_fuel_gallons: Decimal = ZERO
    debug_trace: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class FuelOptimizationContext:
    route: Route
    vehicle: Vehicle
    initial_fuel_gallons: Decimal
    stations: list[FuelStationCandidate]
    algorithm: FuelOptimizationAlgorithm
    constraints: FuelOptimizationConstraints
    consumption_model: FuelConsumptionModel
    detour_calculator: DetourCalculator


class ConstantMpgFuelConsumptionModel:
    def fuel_required(self, distance_miles: Decimal, vehicle: Vehicle) -> Decimal:
        return distance_miles / vehicle.fuel_profile.consumption_mpg


class GreedyFuelOptimizationStrategy:
    algorithm_version = "1"

    def optimize(self, context: FuelOptimizationContext) -> FuelOptimizationPlan:
        usable = context.vehicle.fuel_profile.usable_tank_capacity_gallons
        reserve = context.constraints.reserve_gallons
        initial = context.initial_fuel_gallons

        if initial < ZERO or initial > usable:
            raise InvalidFuelOptimizationInputError(
                "initial_fuel_gallons must be between 0 and usable_tank_capacity_gallons"
            )
        if initial < reserve:
            return self._infeasible_plan(context, initial)

        stations = sorted(
            context.stations,
            key=lambda item: (item.route_offset_meters, str(item.station_id)),
        )
        current_offset = ZERO
        current_fuel = initial
        total_consumed = ZERO
        total_purchased = ZERO
        total_cost_precise = ZERO
        total_detour_distance = ZERO
        total_detour_time = 0
        current_station: FuelStationCandidate | None = None
        stops: list[FuelOptimizationStop] = []
        debug_trace: list[dict[str, Any]] = [
            {
                "event": "initial_state",
                "message": "Initialized greedy fuel optimization.",
                "status": "initialized",
                "route_total_distance_meters": context.route.total_distance_meters,
                "route_total_distance_miles": context.route.total_distance_meters
                * MILES_PER_METER,
                "initial_fuel_gallons": initial,
                "usable_tank_capacity_gallons": usable,
                "reserve_gallons": reserve,
                "station_count": len(context.stations),
            }
        ]

        while True:
            fuel_to_destination = self._fuel_between(
                context, current_offset, context.route.total_distance_meters, ZERO
            )
            destination_reachable = current_fuel - fuel_to_destination >= reserve

            if destination_reachable:
                remaining = current_fuel - fuel_to_destination
                return self._success_plan(
                    context=context,
                    stops=stops,
                    total_consumed=total_consumed + fuel_to_destination,
                    total_purchased=total_purchased,
                    total_cost_precise=total_cost_precise,
                    total_detour_distance=total_detour_distance,
                    total_detour_time=total_detour_time,
                    remaining_fuel=remaining,
                    debug_trace=debug_trace,
                )

            if current_station is None:
                reachable = self._reachable_stations(
                    context,
                    stations,
                    current_offset,
                    current_fuel,
                    debug_trace=debug_trace,
                    phase="initial_station_search",
                )
                if not reachable:
                    debug_trace.append(
                        {
                            "event": "no_reachable_station_from_origin",
                            "message": "No reachable station was found from the current state.",
                            "current_offset_meters": current_offset,
                            "current_station_id": None,
                            "current_fuel_gallons": current_fuel,
                            "reserve_gallons": reserve,
                        }
                    )
                    return self._infeasible_plan(
                        context, current_fuel, debug_trace=debug_trace
                    )
                next_station = max(
                    reachable,
                    key=lambda item: (
                        item.route_offset_meters,
                        item.fuel_price_per_gallon,
                        str(item.station_id),
                    ),
                )
                fuel_to_station = self._fuel_to_station(
                    context, current_offset, next_station
                )
                debug_trace.append(
                    {
                        "event": "travel_to_initial_station",
                        "message": "Traveled to the farthest reachable station before first refuel.",
                        "reachable_station_count": len(reachable),
                        "selected_station_id": next_station.station_id,
                        "selected_station_price_per_gallon": next_station.fuel_price_per_gallon,
                        "selected_station_route_offset_meters": next_station.route_offset_meters,
                        "selected_station_detour_distance_meters": next_station.detour.distance_meters,
                        "fuel_required_gallons": fuel_to_station,
                        "fuel_before_gallons": current_fuel,
                        "fuel_after_arrival_gallons": current_fuel - fuel_to_station,
                    }
                )
                current_fuel -= fuel_to_station
                total_consumed += fuel_to_station
                current_offset = next_station.route_offset_meters
                current_station = next_station
                continue

            full_reachable = self._reachable_stations(
                context,
                stations,
                current_offset,
                usable,
                debug_trace=debug_trace,
                phase="search_with_full_tank",
            )
            cheaper_ahead = next(
                (
                    item
                    for item in full_reachable
                    if item.route_offset_meters > current_offset
                    and item.fuel_price_per_gallon
                    < current_station.fuel_price_per_gallon
                ),
                None,
            )
            debug_trace.append(
                {
                    "event": "lookahead_for_cheaper_station",
                    "message": "Searched for a cheaper reachable station ahead, assuming full tank.",
                    "current_station_id": current_station.station_id,
                    "current_station_price_per_gallon": current_station.fuel_price_per_gallon,
                    "full_tank_reachable_count": len(full_reachable),
                    "cheaper_station_found": cheaper_ahead is not None,
                    "cheaper_station_id": cheaper_ahead.station_id
                    if cheaper_ahead is not None
                    else None,
                    "cheaper_station_price_per_gallon": cheaper_ahead.fuel_price_per_gallon
                    if cheaper_ahead is not None
                    else None,
                    "price_difference_per_gallon": (
                        current_station.fuel_price_per_gallon
                        - cheaper_ahead.fuel_price_per_gallon
                    )
                    if cheaper_ahead is not None
                    else None,
                }
            )

            if cheaper_ahead is not None:
                desired_fuel_after = (
                    self._fuel_to_station(
                        context,
                        current_offset,
                        cheaper_ahead,
                    )
                    + reserve
                )
                next_target = cheaper_ahead
                decision_reason = "buy_minimum_to_reach_cheaper_station_plus_reserve"
            else:
                desired_fuel_after = min(
                    usable,
                    self._fuel_between(
                        context,
                        current_offset,
                        context.route.total_distance_meters,
                        ZERO,
                    )
                    + reserve,
                )
                next_target = None
                decision_reason = (
                    "buy_enough_for_destination_or_until_next_reachable_segment"
                )

            desired_fuel_after = min(desired_fuel_after, usable)
            max_additional = usable - current_fuel
            fuel_added = max(ZERO, desired_fuel_after - current_fuel)
            fuel_added = min(fuel_added, max_additional)

            min_refuel = context.vehicle.fuel_profile.min_refuel_gallons
            if fuel_added > ZERO and min_refuel is not None and fuel_added < min_refuel:
                fuel_added = min(min_refuel, max_additional)
            max_refuel = context.vehicle.fuel_profile.max_refuel_gallons
            if max_refuel is not None:
                fuel_added = min(fuel_added, max_refuel)

            fuel_after = current_fuel + fuel_added
            if fuel_after > usable:
                fuel_after = usable
                fuel_added = usable - current_fuel

            fuel_cost_precise = ZERO
            if fuel_added > ZERO:
                fuel_cost_precise = fuel_added * current_station.fuel_price_per_gallon
                total_purchased += fuel_added
                total_cost_precise += fuel_cost_precise
                total_detour_distance += current_station.detour.distance_meters
                total_detour_time += current_station.detour.time_seconds
                stops.append(
                    FuelOptimizationStop(
                        sequence=len(stops) + 1,
                        station_id=current_station.station_id,
                        route_offset_meters=_q4(current_station.route_offset_meters),
                        fuel_before_gallons=_q4(current_fuel),
                        fuel_added_gallons=_q4(fuel_added),
                        fuel_after_gallons=_q4(fuel_after),
                        fuel_price_per_gallon=_q4(
                            current_station.fuel_price_per_gallon
                        ),
                        fuel_cost=_money(fuel_cost_precise),
                        detour_distance_meters=_q2(
                            current_station.detour.distance_meters
                        ),
                        detour_time_seconds=current_station.detour.time_seconds,
                    )
                )

            debug_trace.append(
                {
                    "event": "refuel_decision",
                    "message": "Computed how much fuel to buy at the current station.",
                    "decision_reason": decision_reason,
                    "current_station_id": current_station.station_id,
                    "current_station_price_per_gallon": current_station.fuel_price_per_gallon,
                    "fuel_before_gallons": current_fuel,
                    "desired_fuel_after_gallons": desired_fuel_after,
                    "usable_tank_capacity_gallons": usable,
                    "max_additional_fuel_gallons": max_additional,
                    "min_refuel_gallons": min_refuel,
                    "max_refuel_gallons": max_refuel,
                    "fuel_added_gallons": fuel_added,
                    "fuel_after_gallons": fuel_after,
                    "fuel_cost": _money(fuel_cost_precise),
                    "next_target_station_id": next_target.station_id
                    if next_target is not None
                    else None,
                }
            )

            current_fuel = fuel_after

            if next_target is None:
                if self._destination_reachable(
                    context, current_offset, current_fuel, reserve
                ):
                    debug_trace.append(
                        {
                            "event": "destination_reachable",
                            "message": "After refueling, the destination became reachable.",
                            "current_offset_meters": current_offset,
                            "current_fuel_gallons": current_fuel,
                            "remaining_distance_meters": max(
                                ZERO,
                                context.route.total_distance_meters - current_offset,
                            ),
                            "reserve_gallons": reserve,
                        }
                    )
                    continue
                reachable_after_refuel = self._reachable_stations(
                    context,
                    stations,
                    current_offset,
                    current_fuel,
                    debug_trace=debug_trace,
                    phase="search_after_refuel",
                )
                if not reachable_after_refuel:
                    debug_trace.append(
                        {
                            "event": "no_reachable_station_after_refuel",
                            "message": "After refueling, neither destination nor any next station is reachable.",
                            "current_offset_meters": current_offset,
                            "current_station_id": current_station.station_id,
                            "current_fuel_gallons": current_fuel,
                            "reserve_gallons": reserve,
                        }
                    )
                    return self._infeasible_plan(
                        context, current_fuel, debug_trace=debug_trace
                    )
                next_target = max(
                    reachable_after_refuel,
                    key=lambda item: (
                        item.route_offset_meters,
                        -item.fuel_price_per_gallon,
                        str(item.station_id),
                    ),
                )

            fuel_to_station = self._fuel_to_station(
                context, current_offset, next_target
            )
            if current_fuel - fuel_to_station < reserve:
                debug_trace.append(
                    {
                        "event": "next_station_became_unreachable",
                        "message": "The planned next station cannot be reached without violating reserve.",
                        "reason": "insufficient_fuel_for_travel",
                        "current_station_id": current_station.station_id,
                        "planned_next_station_id": next_target.station_id,
                        "fuel_before_travel_gallons": current_fuel,
                        "fuel_required_for_travel_gallons": fuel_to_station,
                        "projected_fuel_after_arrival_gallons": current_fuel
                        - fuel_to_station,
                        "reserve_gallons": reserve,
                        "fuel_deficit_gallons": reserve
                        - (current_fuel - fuel_to_station),
                    }
                )
                return self._infeasible_plan(
                    context, current_fuel, debug_trace=debug_trace
                )
            debug_trace.append(
                {
                    "event": "travel_to_next_station",
                    "message": "Departed current station and traveled to the selected next station.",
                    "selected_station_id": next_target.station_id,
                    "selected_station_price_per_gallon": next_target.fuel_price_per_gallon,
                    "selected_station_route_offset_meters": next_target.route_offset_meters,
                    "selected_station_detour_distance_meters": next_target.detour.distance_meters,
                    "fuel_before_departure_gallons": current_fuel,
                    "fuel_required_for_travel_gallons": fuel_to_station,
                    "fuel_after_arrival_gallons": current_fuel - fuel_to_station,
                }
            )
            current_fuel -= fuel_to_station
            total_consumed += fuel_to_station
            current_offset = next_target.route_offset_meters
            current_station = next_target

    def _reachable_stations(
        self,
        context: FuelOptimizationContext,
        stations: list[FuelStationCandidate],
        current_offset: Decimal,
        current_fuel: Decimal,
        *,
        debug_trace: list[dict[str, Any]] | None = None,
        phase: str,
    ) -> list[FuelStationCandidate]:
        reserve = context.constraints.reserve_gallons
        reachable: list[FuelStationCandidate] = []
        skipped_behind: list[tuple[UUID, Decimal]] = []
        unreachable_due_to_fuel: list[tuple[UUID, Decimal, Decimal]] = []

        for station in stations:
            if station.route_offset_meters <= current_offset:
                skipped_behind.append((station.station_id, station.route_offset_meters))
                continue
            fuel_needed = self._fuel_to_station(context, current_offset, station)
            projected_after_arrival = current_fuel - fuel_needed
            reachable_now = projected_after_arrival >= reserve
            if not reachable_now:
                unreachable_due_to_fuel.append(
                    (
                        station.station_id,
                        station.fuel_price_per_gallon,
                        projected_after_arrival,
                    )
                )
            else:
                reachable.append(station)

        if debug_trace is not None:
            evaluation_summary = {
                "event": "stations_evaluated",
                "phase": phase,
                "message": f"Evaluated {len(stations)} station(s) for reachability.",
                "total_stations_evaluated": len(stations),
                "skipped_behind_current_offset_count": len(skipped_behind),
                "unreachable_due_to_fuel_count": len(unreachable_due_to_fuel),
                "reachable_count": len(reachable),
                "current_offset_meters": current_offset,
                "current_fuel_gallons": current_fuel,
                "reserve_gallons": reserve,
            }
            if skipped_behind:
                evaluation_summary["skipped_behind_sample"] = [
                    {
                        "station_id": str(sid),
                        "station_route_offset_meters": _q2(offset),
                    }
                    for sid, offset in skipped_behind[:3]
                ]
                if len(skipped_behind) > 3:
                    evaluation_summary["skipped_behind_omitted_count"] = (
                        len(skipped_behind) - 3
                    )
            if unreachable_due_to_fuel:
                evaluation_summary["unreachable_sample"] = [
                    {
                        "station_id": str(sid),
                        "projected_fuel_after_arrival_gallons": _q4(fuel),
                    }
                    for sid, _, fuel in unreachable_due_to_fuel[:3]
                ]
                if len(unreachable_due_to_fuel) > 3:
                    evaluation_summary["unreachable_omitted_count"] = (
                        len(unreachable_due_to_fuel) - 3
                    )
            debug_trace.append(evaluation_summary)

        return reachable

    def _destination_reachable(
        self,
        context: FuelOptimizationContext,
        current_offset: Decimal,
        current_fuel: Decimal,
        reserve: Decimal,
    ) -> bool:
        fuel_to_destination = self._fuel_between(
            context, current_offset, context.route.total_distance_meters, ZERO
        )
        return current_fuel - fuel_to_destination >= reserve

    def _fuel_to_station(
        self,
        context: FuelOptimizationContext,
        current_offset: Decimal,
        station: FuelStationCandidate,
    ) -> Decimal:
        return self._fuel_between(
            context,
            current_offset,
            station.route_offset_meters,
            station.detour.distance_meters,
        )

    def _fuel_between(
        self,
        context: FuelOptimizationContext,
        current_offset: Decimal,
        target_offset: Decimal,
        detour_distance_meters: Decimal,
    ) -> Decimal:
        route_distance = max(ZERO, target_offset - current_offset)
        travel_distance_miles = (
            route_distance + detour_distance_meters
        ) * MILES_PER_METER
        return context.consumption_model.fuel_required(
            travel_distance_miles, context.vehicle
        )

    def _success_plan(
        self,
        *,
        context: FuelOptimizationContext,
        stops: list[FuelOptimizationStop],
        total_consumed: Decimal,
        total_purchased: Decimal,
        total_cost_precise: Decimal,
        total_detour_distance: Decimal,
        total_detour_time: int,
        remaining_fuel: Decimal,
        debug_trace: list[dict[str, Any]],
    ) -> FuelOptimizationPlan:
        debug_trace.append(
            {
                "event": "optimization_completed_successfully",
                "message": "Fuel optimization finished with a feasible plan.",
                "status": "success",
                "total_fuel_consumed_gallons": total_consumed,
                "total_fuel_purchased_gallons": total_purchased,
                "total_cost": _money(total_cost_precise),
                "total_detour_distance_meters": total_detour_distance,
                "total_detour_time_seconds": total_detour_time,
                "remaining_fuel_gallons": remaining_fuel,
                "number_of_stops": len(stops),
            }
        )
        return FuelOptimizationPlan(
            algorithm=context.algorithm,
            algorithm_version=self.algorithm_version,
            vehicle_id=context.vehicle.id,
            route_id=context.route.id,
            status=FuelOptimizationStatus.SUCCESS,
            stops=stops,
            total_fuel_consumed_gallons=_q4(total_consumed),
            total_fuel_purchased_gallons=_q4(total_purchased),
            total_fuel_cost=_money(total_cost_precise),
            total_detour_distance_meters=_q2(total_detour_distance),
            total_detour_time_seconds=total_detour_time,
            number_of_stops=len(stops),
            remaining_fuel_gallons=_q4(remaining_fuel),
            debug_trace=debug_trace,
        )

    def _infeasible_plan(
        self,
        context: FuelOptimizationContext,
        remaining_fuel: Decimal,
        *,
        debug_trace: list[dict[str, Any]] | None = None,
    ) -> FuelOptimizationPlan:
        final_trace = list(debug_trace or [])
        final_trace.append(
            {
                "event": "optimization_infeasible",
                "message": "Fuel optimization could not find a feasible continuation while preserving reserve.",
                "remaining_fuel_gallons": remaining_fuel,
            }
        )
        return FuelOptimizationPlan(
            algorithm=context.algorithm,
            algorithm_version=self.algorithm_version,
            vehicle_id=context.vehicle.id,
            route_id=context.route.id,
            status=FuelOptimizationStatus.INFEASIBLE,
            remaining_fuel_gallons=_q4(remaining_fuel),
            debug_trace=final_trace,
        )


class FuelOptimizationEngine:
    def __init__(self, registry: FuelOptimizationStrategyRegistry):
        self.registry = registry

    def optimize(self, request: FuelOptimizationContext) -> FuelOptimizationPlan:
        strategy = self.registry.get(request.algorithm)
        return strategy.optimize(request)


class FuelOptimizationStrategyRegistry:
    def __init__(
        self, strategies: dict[FuelOptimizationAlgorithm, FuelOptimizationStrategy]
    ):
        self._strategies = strategies

    def get(self, algorithm: FuelOptimizationAlgorithm) -> FuelOptimizationStrategy:
        strategy = self._strategies.get(algorithm)
        if strategy is None:
            raise UnsupportedOptimizationAlgorithmError(str(algorithm))
        return strategy


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _q4(value: Decimal) -> Decimal:
    return value.quantize(FUEL_QUANT, rounding=ROUND_HALF_UP)


def _q2(value: Decimal) -> Decimal:
    return value.quantize(DISTANCE_QUANT, rounding=ROUND_HALF_UP)
