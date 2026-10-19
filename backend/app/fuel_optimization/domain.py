from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any, Literal, Protocol
from uuid import UUID

MONEY_QUANT = Decimal("0.01")
FUEL_QUANT = Decimal("0.0001")
DISTANCE_QUANT = Decimal("0.01")
ZERO = Decimal("0")
MILES_PER_METER = Decimal("0.000621371192237334")
SECONDS_PER_HOUR = Decimal("3600")
SECONDS_PER_MINUTE = Decimal("60")


class FuelOptimizationAlgorithm(StrEnum):
    GREEDY = "greedy"


class FuelOptimizationStatus(StrEnum):
    SUCCESS = "success"
    INFEASIBLE = "infeasible"


class FuelOptimizationFailureReason(StrEnum):
    INITIAL_FUEL_BELOW_RESERVE = "initial_fuel_below_reserve"
    NO_REACHABLE_STATION = "no_reachable_station"
    NO_REACHABLE_CONTINUATION = "no_reachable_continuation"
    PLANNED_STATION_UNREACHABLE = "planned_station_unreachable"
    DESTINATION_UNREACHABLE = "destination_unreachable"


class UnsupportedOptimizationAlgorithmError(Exception):
    pass


class InvalidFuelOptimizationInputError(Exception):
    pass


@dataclass(frozen=True)
class Vehicle:
    id: UUID
    name: str
    unit_number: str
    vehicle_type: str
    fuel_type: str
    tank_capacity_gallons: Decimal
    usable_tank_capacity_gallons: Decimal
    consumption_mpg: Decimal

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
    name: str = ""


@dataclass(frozen=True)
class FuelOptimizationConstraints:
    reserve_gallons: Decimal
    min_refuel_gallons: Decimal | None = None
    max_refuel_gallons: Decimal | None = None
    max_allowed_detour_meters: Decimal | None = None


@dataclass(frozen=True)
class StopEconomics:
    """Costs of making a refuelling stop that are not the fuel price itself.

    Used to turn a raw price per gallon into an effective one (defects A1/A2):
    a station that is $0.02 cheaper but 8 km off the route and 30 minutes of
    dwell time away is not actually cheaper.

    Money is expressed in the same currency as ``fuel_price_per_gallon``.

    All-zero values (the defaults) disable only the *time* part of the model:
    the fuel burnt on the detour is always priced in, so plans still differ from
    ``algorithm_version = "7"`` whenever a candidate sits off the route.

    Note that ``dwell_minutes`` is priced through ``downtime_cost_per_hour``, so
    it has no effect on its own — enable the two together.

    ``downtime_cost_per_hour`` is the cost of an hour the *whole truck* spends
    not earning, not just the driver's wage. It is a single lump figure that
    should cover everything that keeps accruing while the truck stands still:

    * driver pay including payroll taxes and benefits;
    * vehicle holding cost (lease or depreciation, insurance, permits);
    * optionally, the revenue lost per hour (rate per mile x average speed).

    Count each item once: if lost revenue is already included, do not add the
    driver's pay on top of it. Fuel is excluded, it is priced separately.
    """

    #: Cost of one hour of truck downtime, currency units per hour (see above).
    downtime_cost_per_hour: Decimal = ZERO
    #: Minutes spent leaving the route, fuelling and getting back on it.
    dwell_minutes: Decimal = ZERO
    #: Flat per-stop charge (parking, service fees); excludes the time cost.
    fixed_stop_cost: Decimal = ZERO

    def __post_init__(self) -> None:
        if self.downtime_cost_per_hour < ZERO:
            raise InvalidFuelOptimizationInputError(
                "downtime_cost_per_hour must be greater than or equal to 0"
            )
        if self.dwell_minutes < ZERO:
            raise InvalidFuelOptimizationInputError(
                "dwell_minutes must be greater than or equal to 0"
            )
        if self.fixed_stop_cost < ZERO:
            raise InvalidFuelOptimizationInputError(
                "fixed_stop_cost must be greater than or equal to 0"
            )

    def cost_of_seconds(self, seconds: Decimal) -> Decimal:
        """Price a duration, multiplying before dividing to stay exact.

        ``75 / 3600`` is a repeating decimal, so scaling the rate first would
        leak rounding error into every comparison.
        """
        return (seconds * self.downtime_cost_per_hour) / SECONDS_PER_HOUR

    @property
    def dwell_seconds(self) -> Decimal:
        return self.dwell_minutes * SECONDS_PER_MINUTE

    @property
    def is_neutral(self) -> bool:
        return (
            self.downtime_cost_per_hour == ZERO
            and self.dwell_minutes == ZERO
            and self.fixed_stop_cost == ZERO
        )


@dataclass(frozen=True)
class FuelOptimizationRequest:
    route_id: UUID
    vehicle_id: UUID
    initial_fuel_gallons: Decimal
    algorithm: FuelOptimizationAlgorithm = FuelOptimizationAlgorithm.GREEDY
    constraints: FuelOptimizationConstraints | None = None


class FuelConsumptionModel(Protocol):
    def fuel_required(self, distance_miles: Decimal, vehicle: Vehicle) -> Decimal: ...


class StationCostModel(Protocol):
    def stop_time_cost(self, station: FuelStationCandidate) -> Decimal: ...

    def stop_overhead_cost(
        self, station: FuelStationCandidate, vehicle: Vehicle | None = None
    ) -> Decimal: ...

    def effective_price_per_gallon(
        self,
        station: FuelStationCandidate,
        volume_gallons: Decimal,
        detour_fuel_gallons: Decimal = ZERO,
    ) -> Decimal | None: ...


class DetourCalculator(Protocol):
    def calculate(self, distance_from_route_meters: Decimal) -> Detour: ...


class FuelOptimizationStrategy(Protocol):
    def optimize(self, context: FuelOptimizationContext) -> FuelOptimizationPlan: ...


@dataclass(frozen=True)
class StationAlternative:
    """A station that was weighed against the chosen one and lost (or was out of reach).

    ``outcome`` is one of ``higher_effective_price``, ``tie_broken_by_distance``,
    ``no_fuel_to_buy``, ``not_reachable`` or ``overhead_exceeds_savings``.
    """

    station_id: UUID
    name: str
    latitude: Decimal
    longitude: Decimal
    route_offset_meters: Decimal
    fuel_price_per_gallon: Decimal
    detour_distance_meters: Decimal
    detour_time_seconds: int
    cheaper_by_sticker: bool
    outcome: str
    effective_price_per_gallon: Decimal | None = None
    delta_vs_chosen_per_gallon: Decimal | None = None
    total_extra_cost: Decimal | None = None
    estimated_savings: Decimal | None = None
    stop_overhead_cost: Decimal | None = None


@dataclass(frozen=True)
class StationSelection:
    """Why the optimizer drove to a station, with the numbers it used.

    ``rule`` is ``lowest_effective_price`` (mandatory stop, candidates compared
    by effective price) or ``cheaper_ahead_pays_off`` (an optional extra stop
    whose savings beat its overhead).

    For ``lowest_effective_price`` the premium over the sticker price satisfies
    ``premium_per_gallon * delivered_gallons == detour_fuel_cost + time_cost +
    fixed_stop_cost``. ``cheaper_ahead_pays_off`` has no per-gallon figure:
    the decision is ``estimated_savings - stop_overhead_cost``.
    """

    rule: str
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
    alternatives: list[StationAlternative] = field(default_factory=list)
    alternatives_omitted_count: int = 0
    next_stop_mandatory: bool = False


@dataclass(frozen=True)
class LookaheadDecision:
    """What was decided at a stop about continuing to a cheaper station ahead.

    ``rule``: ``cheaper_ahead_pays_off`` (bought the minimum to reach it),
    ``cheaper_ahead_rejected`` (it was cheaper, but its overhead outweighed the
    savings, so the tank was filled here) or ``no_cheaper_ahead``.
    """

    rule: str
    station_id: UUID | None = None
    station_name: str | None = None
    price_difference_per_gallon: Decimal | None = None
    estimated_savings: Decimal | None = None
    stop_overhead_cost: Decimal | None = None
    shifted_volume_gallons: Decimal | None = None


@dataclass(frozen=True)
class _LookaheadEvaluation:
    station: FuelStationCandidate
    savings: Decimal
    overhead: Decimal
    shifted_volume: Decimal


@dataclass(frozen=True)
class _LookaheadResult:
    chosen: _LookaheadEvaluation | None
    rejected: list[_LookaheadEvaluation]


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
    selection: StationSelection | None = None
    lookahead: LookaheadDecision | None = None


@dataclass(frozen=True)
class FuelOptimizationReachedStation:
    station_id: UUID
    name: str
    route_offset_meters: Decimal
    latitude: Decimal
    longitude: Decimal
    fuel_gallons: Decimal


FailureTargetKind = Literal["start", "station", "destination"]


@dataclass(frozen=True)
class FuelOptimizationFailureTarget:
    kind: FailureTargetKind
    station_id: UUID | None
    name: str
    route_offset_meters: Decimal
    latitude: Decimal
    longitude: Decimal
    fuel_required_gallons: Decimal
    available_fuel_gallons: Decimal
    reserve_gallons: Decimal
    projected_arrival_fuel_gallons: Decimal
    deficit_gallons: Decimal


@dataclass(frozen=True)
class FuelOptimizationFailure:
    reason: FuelOptimizationFailureReason
    stopped_at_route_offset_meters: Decimal
    last_reachable_station_id: UUID | None
    last_reachable_route_offset_meters: Decimal
    available_fuel_gallons: Decimal
    reserve_gallons: Decimal
    primary_target: FuelOptimizationFailureTarget
    unreachable_stations: list[FuelOptimizationFailureTarget] = field(
        default_factory=list
    )
    destination: FuelOptimizationFailureTarget | None = None


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
    reached_stations: list[FuelOptimizationReachedStation] = field(default_factory=list)
    failure: FuelOptimizationFailure | None = None
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
    stop_economics: StopEconomics = field(default_factory=StopEconomics)


class ConstantMpgFuelConsumptionModel:
    def fuel_required(self, distance_miles: Decimal, vehicle: Vehicle) -> Decimal:
        return distance_miles / vehicle.consumption_mpg


class EconomicStationCostModel:
    """Prices a refuelling stop including detour and time overhead.

    Two different questions need two different formulas:

    * "which reachable station should we drive to" — the stop is mandatory and
      the candidates are mutually exclusive, so compare the full cost reduced to
      a per-gallon figure via :meth:`effective_price_per_gallon`. The fuel burnt
      on the detour must **not** be added to the numerator there: it is already
      charged by ``_fuel_to_station`` and therefore already inflates the volume
      to buy. It is discounted from the delivered volume instead.
    * "should we buy the minimum here and refill at a cheaper station ahead" —
      the extra stop is optional, so compare the savings against
      :meth:`stop_overhead_cost`, where the detour fuel *is* an extra cost.
    """

    def __init__(self, economics: StopEconomics):
        self.economics = economics

    def stop_time_cost(self, station: FuelStationCandidate) -> Decimal:
        seconds = Decimal(station.detour.time_seconds) + self.economics.dwell_seconds
        return self.economics.cost_of_seconds(seconds)

    def detour_fuel_gallons(
        self, station: FuelStationCandidate, vehicle: Vehicle
    ) -> Decimal:
        miles = station.detour.distance_meters * MILES_PER_METER
        return miles / vehicle.consumption_mpg

    def stop_overhead_cost(
        self, station: FuelStationCandidate, vehicle: Vehicle | None = None
    ) -> Decimal:
        overhead = self.stop_time_cost(station) + self.economics.fixed_stop_cost
        if vehicle is not None:
            overhead += (
                self.detour_fuel_gallons(station, vehicle)
                * station.fuel_price_per_gallon
            )
        return overhead

    def effective_price_per_gallon(
        self,
        station: FuelStationCandidate,
        volume_gallons: Decimal,
        detour_fuel_gallons: Decimal = ZERO,
    ) -> Decimal | None:
        """Cost of one gallon that actually moves the truck along the route.

        ``volume_gallons`` already includes the fuel burnt on the detour (it is
        charged by ``_fuel_to_station``), so that fuel must not be added to the
        numerator again. It is instead removed from the denominator: those
        gallons are paid for but deliver no route progress. With zero detours
        and neutral economics this collapses to the raw price per gallon.
        """
        delivered = volume_gallons - detour_fuel_gallons
        if volume_gallons <= ZERO or delivered <= ZERO:
            return None
        overhead = self.stop_time_cost(station) + self.economics.fixed_stop_cost
        return (volume_gallons * station.fuel_price_per_gallon + overhead) / delivered


class GreedyFuelOptimizationStrategy:
    # Changelog:
    #   "7" — stations compared by raw fuel_price_per_gallon.
    #   "8" — detour and stop time priced in (defects A1/A2): station choice uses
    #         the effective price per gallon and the "refill at a cheaper station
    #         ahead" decision compares savings against the stop overhead.
    algorithm_version = "8"

    def optimize(self, context: FuelOptimizationContext) -> FuelOptimizationPlan:
        usable = context.vehicle.usable_tank_capacity_gallons
        reserve = context.constraints.reserve_gallons
        initial = context.initial_fuel_gallons
        cost_model = EconomicStationCostModel(context.stop_economics)

        if initial < ZERO or initial > usable:
            raise InvalidFuelOptimizationInputError(
                "initial_fuel_gallons must be between 0 and usable_tank_capacity_gallons"
            )
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
        # Why the optimizer drove to current_station; attached to its stop.
        current_selection: StationSelection | None = None
        stops: list[FuelOptimizationStop] = []
        reached_stations: list[FuelOptimizationReachedStation] = []
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
                    reached_stations=reached_stations,
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
                    min_arrival_fuel_gallons=(
                        reserve if current_fuel >= reserve else ZERO
                    ),
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
                        context,
                        current_fuel,
                        failure_reason=(
                            FuelOptimizationFailureReason.NO_REACHABLE_STATION
                            if any(
                                current_offset
                                < station.route_offset_meters
                                <= context.route.total_distance_meters
                                for station in stations
                            )
                            else FuelOptimizationFailureReason.DESTINATION_UNREACHABLE
                        ),
                        current_offset=current_offset,
                        current_station=current_station,
                        reached_stations=reached_stations,
                        stops=stops,
                        total_consumed=total_consumed,
                        total_purchased=total_purchased,
                        total_cost_precise=total_cost_precise,
                        total_detour_distance=total_detour_distance,
                        total_detour_time=total_detour_time,
                        debug_trace=debug_trace,
                    )
                (
                    next_station,
                    next_station_effective_price,
                    current_selection,
                ) = self._select_cheapest_reachable(
                    context,
                    cost_model,
                    reachable,
                    current_offset,
                    current_fuel,
                    stations,
                )
                fuel_to_station = self._fuel_to_station(
                    context, current_offset, next_station
                )
                debug_trace.append(
                    {
                        "event": "travel_to_initial_station",
                        "message": "Traveled to the station with the lowest effective price (detour time and stop cost included).",
                        "reachable_station_count": len(reachable),
                        "selected_station_id": next_station.station_id,
                        "selected_station_price_per_gallon": next_station.fuel_price_per_gallon,
                        "selected_station_effective_price_per_gallon": next_station_effective_price,
                        "selected_station_stop_time_cost": cost_model.stop_time_cost(
                            next_station
                        ),
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
                reached_stations.append(
                    FuelOptimizationReachedStation(
                        station_id=next_station.station_id,
                        name=next_station.name,
                        route_offset_meters=_q4(next_station.route_offset_meters),
                        latitude=next_station.latitude,
                        longitude=next_station.longitude,
                        fuel_gallons=_q4(current_fuel),
                    )
                )
                continue

            full_reachable = self._reachable_stations(
                context,
                stations,
                current_offset,
                usable,
                debug_trace=debug_trace,
                phase="search_with_full_tank",
            )
            fuel_to_destination = self._fuel_between(
                context, current_offset, context.route.total_distance_meters, ZERO
            )
            fill_here_target = min(usable, fuel_to_destination + reserve)
            # If a full tank is not enough to finish the route, the next stop is
            # unavoidable: its overhead is not an extra cost of this decision.
            next_stop_is_mandatory = usable - fuel_to_destination < reserve
            lookahead_result = self._select_cheaper_station_ahead(
                context,
                cost_model,
                full_reachable,
                current_offset,
                current_station,
                fill_here_target,
                reserve,
                charge_overhead=not next_stop_is_mandatory,
            )
            chosen_ahead = lookahead_result.chosen
            cheaper_ahead = chosen_ahead.station if chosen_ahead else None
            cheaper_ahead_savings = chosen_ahead.savings if chosen_ahead else None
            cheaper_ahead_overhead = chosen_ahead.overhead if chosen_ahead else None
            cheaper_ahead_shifted_volume = (
                chosen_ahead.shifted_volume if chosen_ahead else None
            )
            rejected_by_overhead = bool(lookahead_result.rejected)
            lookahead_decision = self._lookahead_decision(
                lookahead_result, current_station
            )
            next_selection: StationSelection | None = None
            if chosen_ahead is not None:
                next_selection = self._lookahead_selection(
                    context,
                    cost_model,
                    lookahead_result,
                    full_reachable,
                    current_offset,
                    current_station,
                    next_stop_is_mandatory=next_stop_is_mandatory,
                )
            debug_trace.append(
                {
                    "event": "lookahead_for_cheaper_station",
                    "message": "Searched ahead for a station whose savings outweigh the cost of an extra stop (full tank assumed).",
                    "current_station_id": current_station.station_id,
                    "current_station_price_per_gallon": current_station.fuel_price_per_gallon,
                    "full_tank_reachable_count": len(full_reachable),
                    "next_stop_is_mandatory": next_stop_is_mandatory,
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
                    "shifted_volume_gallons": cheaper_ahead_shifted_volume,
                    "estimated_savings": cheaper_ahead_savings,
                    "stop_overhead_cost": cheaper_ahead_overhead,
                    "rejected_because_overhead_exceeds_savings": rejected_by_overhead,
                }
            )

            if cheaper_ahead is not None:
                desired_fuel_after = _q4_ceil(
                    self._fuel_to_station(context, current_offset, cheaper_ahead)
                    + reserve
                )
                next_target = cheaper_ahead
                decision_reason = "buy_minimum_to_reach_cheaper_station_plus_reserve"
            else:
                desired_fuel_after = min(
                    usable,
                    _q4_ceil(
                        self._fuel_between(
                            context,
                            current_offset,
                            context.route.total_distance_meters,
                            ZERO,
                        )
                        + reserve
                    ),
                )
                next_target = None
                decision_reason = (
                    "buy_enough_for_destination_or_until_next_reachable_segment"
                )

            desired_fuel_after = min(desired_fuel_after, usable)
            max_additional = usable - current_fuel
            fuel_added = max(ZERO, desired_fuel_after - current_fuel)
            fuel_added = min(fuel_added, max_additional)

            min_refuel = context.constraints.min_refuel_gallons
            if fuel_added > ZERO and min_refuel is not None:
                # The minimum cannot be bought here, so skip refuelling at this station.
                if max_additional < min_refuel:
                    fuel_added = ZERO
                elif fuel_added < min_refuel:
                    fuel_added = min_refuel
            max_refuel = context.constraints.max_refuel_gallons
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
                        selection=current_selection,
                        lookahead=lookahead_decision,
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
                        context,
                        current_fuel,
                        failure_reason=(
                            FuelOptimizationFailureReason.NO_REACHABLE_CONTINUATION
                            if any(
                                current_offset
                                < station.route_offset_meters
                                <= context.route.total_distance_meters
                                for station in stations
                            )
                            else FuelOptimizationFailureReason.DESTINATION_UNREACHABLE
                        ),
                        current_offset=current_offset,
                        current_station=current_station,
                        reached_stations=reached_stations,
                        stops=stops,
                        total_consumed=total_consumed,
                        total_purchased=total_purchased,
                        total_cost_precise=total_cost_precise,
                        total_detour_distance=total_detour_distance,
                        total_detour_time=total_detour_time,
                        debug_trace=debug_trace,
                    )
                next_target, _, next_selection = self._select_cheapest_reachable(
                    context,
                    cost_model,
                    reachable_after_refuel,
                    current_offset,
                    current_fuel,
                    stations,
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
                    context,
                    current_fuel,
                    failure_reason=FuelOptimizationFailureReason.PLANNED_STATION_UNREACHABLE,
                    current_offset=current_offset,
                    current_station=current_station,
                    reached_stations=reached_stations,
                    stops=stops,
                    total_consumed=total_consumed,
                    total_purchased=total_purchased,
                    total_cost_precise=total_cost_precise,
                    total_detour_distance=total_detour_distance,
                    total_detour_time=total_detour_time,
                    debug_trace=debug_trace,
                )
            debug_trace.append(
                {
                    "event": "travel_to_next_station",
                    "message": "Departed current station and traveled to the selected next station.",
                    "selected_station_id": next_target.station_id,
                    "selected_station_price_per_gallon": next_target.fuel_price_per_gallon,
                    "selected_station_stop_time_cost": cost_model.stop_time_cost(
                        next_target
                    ),
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
            current_selection = next_selection
            reached_stations.append(
                FuelOptimizationReachedStation(
                    station_id=next_target.station_id,
                    name=next_target.name,
                    route_offset_meters=_q4(next_target.route_offset_meters),
                    latitude=next_target.latitude,
                    longitude=next_target.longitude,
                    fuel_gallons=_q4(current_fuel),
                )
            )

    def _reachable_stations(
        self,
        context: FuelOptimizationContext,
        stations: list[FuelStationCandidate],
        current_offset: Decimal,
        current_fuel: Decimal,
        *,
        debug_trace: list[dict[str, Any]] | None = None,
        phase: str,
        min_arrival_fuel_gallons: Decimal | None = None,
    ) -> list[FuelStationCandidate]:
        reserve = context.constraints.reserve_gallons
        min_arrival = (
            reserve if min_arrival_fuel_gallons is None else min_arrival_fuel_gallons
        )
        reachable: list[FuelStationCandidate] = []
        skipped_behind: list[tuple[UUID, Decimal]] = []
        unreachable_due_to_fuel: list[tuple[UUID, Decimal, Decimal]] = []

        for station in stations:
            # skip stations beyond route end (defensive fallback)
            if station.route_offset_meters > context.route.total_distance_meters:
                continue
            if station.route_offset_meters <= current_offset:
                skipped_behind.append((station.station_id, station.route_offset_meters))
                continue
            fuel_needed = self._fuel_to_station(context, current_offset, station)
            projected_after_arrival = current_fuel - fuel_needed
            reachable_now = projected_after_arrival >= min_arrival
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

    def _select_cheaper_station_ahead(
        self,
        context: FuelOptimizationContext,
        cost_model: EconomicStationCostModel,
        full_reachable: list[FuelStationCandidate],
        current_offset: Decimal,
        current_station: FuelStationCandidate,
        fill_here_target: Decimal,
        reserve: Decimal,
        *,
        charge_overhead: bool,
    ) -> _LookaheadResult:
        """Decide whether buying the minimum here and refilling ahead pays off.

        Instead of the raw ``candidate.price < current.price`` test, the volume
        that would move to the candidate is priced against the cost of the extra
        stop: the fuel burnt on the detour (genuinely extra here, unlike in
        :meth:`_select_cheapest_reachable`), the downtime cost and the fixed cost.

        Returns the nearest candidate that pays off and every cheaper candidate
        evaluated (and rejected) before it, with the figures used for each.
        """
        rejected: list[_LookaheadEvaluation] = []

        for station in full_reachable:
            if station.route_offset_meters <= current_offset:
                continue
            if station.fuel_price_per_gallon >= current_station.fuel_price_per_gallon:
                continue

            fuel_to_candidate = self._fuel_to_station(context, current_offset, station)
            shifted_volume = max(ZERO, fill_here_target - (fuel_to_candidate + reserve))
            savings = (
                current_station.fuel_price_per_gallon - station.fuel_price_per_gallon
            ) * shifted_volume
            overhead = (
                cost_model.stop_overhead_cost(station, context.vehicle)
                if charge_overhead
                else ZERO
            )
            evaluation = _LookaheadEvaluation(
                station=station,
                savings=savings,
                overhead=overhead,
                shifted_volume=shifted_volume,
            )
            if savings > overhead:
                return _LookaheadResult(chosen=evaluation, rejected=rejected)
            rejected.append(evaluation)

        return _LookaheadResult(chosen=None, rejected=rejected)

    def _lookahead_selection(
        self,
        context: FuelOptimizationContext,
        cost_model: EconomicStationCostModel,
        result: _LookaheadResult,
        full_reachable: list[FuelStationCandidate],
        current_offset: Decimal,
        current_station: FuelStationCandidate,
        *,
        next_stop_is_mandatory: bool,
    ) -> StationSelection:
        """Explain a stop that was picked because buying there beats filling here.

        Lists every other station ahead within a full tank: the nearer cheaper
        ones that did not pay off, the cheaper ones further away that were never
        weighed because a nearer one already won, and the ones that are not
        cheaper than the station we left.
        """
        assert result.chosen is not None
        chosen = result.chosen.station
        detour_fuel = cost_model.detour_fuel_gallons(chosen, context.vehicle)
        rejected_by_id = {item.station.station_id: item for item in result.rejected}

        def build(
            station: FuelStationCandidate,
            outcome: str,
            item: _LookaheadEvaluation | None = None,
        ) -> StationAlternative:
            return StationAlternative(
                station_id=station.station_id,
                name=station.name,
                latitude=station.latitude,
                longitude=station.longitude,
                route_offset_meters=_q4(station.route_offset_meters),
                fuel_price_per_gallon=_q4(station.fuel_price_per_gallon),
                detour_distance_meters=_q2(station.detour.distance_meters),
                detour_time_seconds=station.detour.time_seconds,
                cheaper_by_sticker=station.fuel_price_per_gallon
                < chosen.fuel_price_per_gallon,
                outcome=outcome,
                estimated_savings=_money(item.savings) if item else None,
                stop_overhead_cost=_money(item.overhead) if item else None,
            )

        alternatives: list[StationAlternative] = []
        for station in full_reachable:
            if (
                station.station_id == chosen.station_id
                or station.route_offset_meters <= current_offset
            ):
                continue
            rejected = rejected_by_id.get(station.station_id)
            if rejected is not None:
                alternatives.append(
                    build(station, "overhead_exceeds_savings", rejected)
                )
            elif station.fuel_price_per_gallon < current_station.fuel_price_per_gallon:
                alternatives.append(build(station, "nearer_cheaper_station_chosen"))
            else:
                alternatives.append(build(station, "not_cheaper_than_previous"))
        shown, omitted = _rank_alternatives(alternatives)
        return StationSelection(
            rule="cheaper_ahead_pays_off",
            next_stop_mandatory=next_stop_is_mandatory,
            sticker_price_per_gallon=_q4(chosen.fuel_price_per_gallon),
            detour_fuel_gallons=_q4(detour_fuel),
            detour_fuel_cost=_money(detour_fuel * chosen.fuel_price_per_gallon),
            time_cost=_money(cost_model.stop_time_cost(chosen)),
            fixed_stop_cost=_money(cost_model.economics.fixed_stop_cost),
            estimated_savings=_money(result.chosen.savings),
            stop_overhead_cost=_money(result.chosen.overhead),
            shifted_volume_gallons=_q4(result.chosen.shifted_volume),
            alternatives=shown,
            alternatives_omitted_count=omitted,
        )

    @staticmethod
    def _lookahead_decision(
        result: _LookaheadResult, current_station: FuelStationCandidate
    ) -> LookaheadDecision:
        if result.chosen is not None:
            item = result.chosen
            rule = "cheaper_ahead_pays_off"
        elif result.rejected:
            # The near miss is the most informative one to show.
            item = max(
                result.rejected, key=lambda entry: entry.savings - entry.overhead
            )
            rule = "cheaper_ahead_rejected"
        else:
            return LookaheadDecision(rule="no_cheaper_ahead")
        return LookaheadDecision(
            rule=rule,
            station_id=item.station.station_id,
            station_name=item.station.name,
            price_difference_per_gallon=_q4(
                current_station.fuel_price_per_gallon
                - item.station.fuel_price_per_gallon
            ),
            estimated_savings=_money(item.savings),
            stop_overhead_cost=_money(item.overhead),
            shifted_volume_gallons=_q4(item.shifted_volume),
        )

    def _select_cheapest_reachable(
        self,
        context: FuelOptimizationContext,
        cost_model: EconomicStationCostModel,
        candidates: list[FuelStationCandidate],
        current_offset: Decimal,
        current_fuel: Decimal,
        all_stations: list[FuelStationCandidate],
    ) -> tuple[FuelStationCandidate, Decimal | None, StationSelection]:
        """Pick the station with the lowest effective price per gallon.

        The stop is mandatory here, so the detour fuel is not charged on top of
        the purchase: it is already burnt by ``_fuel_to_station`` and therefore
        already inflates the volume to buy. It is discounted from the delivered
        volume instead — see
        :meth:`EconomicStationCostModel.effective_price_per_gallon`.

        Stations whose purchase would deliver nothing (``volume <= 0`` or the
        whole purchase swallowed by the detour) get the worst rank. Ties keep
        the historical behaviour: the farthest station first, then ``station_id``.

        Also returns a :class:`StationSelection` explaining the choice. Its
        alternatives are the other reachable candidates plus stations that are
        cheaper by sticker and within a full tank, but not reachable right now.
        """
        usable = context.vehicle.usable_tank_capacity_gallons
        priced: list[
            tuple[
                tuple[int, Decimal, Decimal, str],
                FuelStationCandidate,
                Decimal | None,
                Decimal,
            ]
        ] = []

        for station in candidates:
            volume = usable - (
                current_fuel - self._fuel_to_station(context, current_offset, station)
            )
            detour_fuel = cost_model.detour_fuel_gallons(station, context.vehicle)
            effective_price = cost_model.effective_price_per_gallon(
                station, volume, detour_fuel
            )
            # max() below: refuellable stations first, then the lowest effective
            # price, then the farthest station, then the highest station_id.
            key = (
                0 if effective_price is None else 1,
                -(effective_price if effective_price is not None else ZERO),
                station.route_offset_meters,
                str(station.station_id),
            )
            priced.append((key, station, effective_price, volume))

        _, best, best_price, best_volume = max(priced, key=lambda item: item[0])

        alternatives: list[StationAlternative] = []
        for _, station, effective_price, _ in priced:
            if station.station_id == best.station_id:
                continue
            if effective_price is None:
                outcome = "no_fuel_to_buy"
            elif best_price is not None and effective_price == best_price:
                outcome = "tie_broken_by_distance"
            else:
                outcome = "higher_effective_price"
            alternatives.append(
                self._alternative(
                    station,
                    outcome=outcome,
                    best=best,
                    effective_price=effective_price,
                    chosen_effective_price=best_price,
                    chosen_volume=best_volume,
                )
            )

        reachable_ids = {station.station_id for station in candidates}
        reserve = context.constraints.reserve_gallons
        for station in all_stations:
            if (
                station.station_id in reachable_ids
                or station.route_offset_meters <= current_offset
                or station.route_offset_meters > context.route.total_distance_meters
                or station.fuel_price_per_gallon >= best.fuel_price_per_gallon
            ):
                continue
            # Only stations a full tank could reach: further ones are just noise.
            if (
                self._fuel_to_station(context, current_offset, station)
                > usable - reserve
            ):
                continue
            alternatives.append(
                self._alternative(
                    station,
                    outcome="not_reachable",
                    best=best,
                    effective_price=None,
                    chosen_effective_price=best_price,
                )
            )

        shown, omitted = _rank_alternatives(alternatives)
        detour_fuel = cost_model.detour_fuel_gallons(best, context.vehicle)
        delivered = best_volume - detour_fuel
        return (
            best,
            best_price,
            StationSelection(
                rule="lowest_effective_price",
                sticker_price_per_gallon=_q4(best.fuel_price_per_gallon),
                detour_fuel_gallons=_q4(detour_fuel),
                detour_fuel_cost=_money(detour_fuel * best.fuel_price_per_gallon),
                time_cost=_money(cost_model.stop_time_cost(best)),
                fixed_stop_cost=_money(cost_model.economics.fixed_stop_cost),
                effective_price_per_gallon=(
                    _q4(best_price) if best_price is not None else None
                ),
                premium_per_gallon=(
                    _q4(best_price - best.fuel_price_per_gallon)
                    if best_price is not None
                    else None
                ),
                volume_gallons=_q4(best_volume),
                delivered_gallons=_q4(delivered),
                alternatives=shown,
                alternatives_omitted_count=omitted,
            ),
        )

    @staticmethod
    def _alternative(
        station: FuelStationCandidate,
        *,
        outcome: str,
        best: FuelStationCandidate,
        effective_price: Decimal | None,
        chosen_effective_price: Decimal | None,
        chosen_volume: Decimal | None = None,
    ) -> StationAlternative:
        delta = (
            effective_price - chosen_effective_price
            if effective_price is not None and chosen_effective_price is not None
            else None
        )
        # Per-gallon gap scaled to the gallons bought at the chosen station, so the
        # user sees the real amount instead of a 1-gallon difference.
        total_extra = (
            _money(delta * chosen_volume)
            if delta is not None
            and chosen_volume is not None
            and outcome == "higher_effective_price"
            else None
        )
        return StationAlternative(
            station_id=station.station_id,
            name=station.name,
            latitude=station.latitude,
            longitude=station.longitude,
            route_offset_meters=_q4(station.route_offset_meters),
            fuel_price_per_gallon=_q4(station.fuel_price_per_gallon),
            detour_distance_meters=_q2(station.detour.distance_meters),
            detour_time_seconds=station.detour.time_seconds,
            cheaper_by_sticker=station.fuel_price_per_gallon
            < best.fuel_price_per_gallon,
            outcome=outcome,
            effective_price_per_gallon=(
                _q4(effective_price) if effective_price is not None else None
            ),
            delta_vs_chosen_per_gallon=_q4(delta) if delta is not None else None,
            total_extra_cost=total_extra,
        )

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
        reached_stations: list[FuelOptimizationReachedStation],
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
            reached_stations=reached_stations,
            debug_trace=debug_trace,
        )

    def _infeasible_plan(
        self,
        context: FuelOptimizationContext,
        remaining_fuel: Decimal,
        *,
        failure_reason: FuelOptimizationFailureReason,
        current_offset: Decimal,
        current_station: FuelStationCandidate | None,
        reached_stations: list[FuelOptimizationReachedStation],
        stops: list[FuelOptimizationStop],
        total_consumed: Decimal,
        total_purchased: Decimal,
        total_cost_precise: Decimal,
        total_detour_distance: Decimal,
        total_detour_time: int,
        debug_trace: list[dict[str, Any]] | None = None,
    ) -> FuelOptimizationPlan:
        final_trace = list(debug_trace or [])
        failure = self._build_failure(
            context,
            failure_reason=failure_reason,
            current_offset=current_offset,
            current_fuel=remaining_fuel,
            current_station=current_station,
        )
        final_trace.append(
            {
                "event": "optimization_infeasible",
                "message": "Fuel optimization could not find a feasible continuation while preserving reserve.",
                "remaining_fuel_gallons": remaining_fuel,
                "failure_reason": failure.reason.value,
                "stopped_at_route_offset_meters": failure.stopped_at_route_offset_meters,
                "last_reachable_station_id": failure.last_reachable_station_id,
                "last_reachable_route_offset_meters": failure.last_reachable_route_offset_meters,
                "primary_target_kind": failure.primary_target.kind,
                "primary_target_station_id": failure.primary_target.station_id,
                "primary_target_route_offset_meters": failure.primary_target.route_offset_meters,
                "fuel_required_gallons": failure.primary_target.fuel_required_gallons,
                "available_fuel_gallons": failure.available_fuel_gallons,
                "reserve_gallons": failure.reserve_gallons,
                "fuel_deficit_gallons": failure.primary_target.deficit_gallons,
            }
        )
        return FuelOptimizationPlan(
            algorithm=context.algorithm,
            algorithm_version=self.algorithm_version,
            vehicle_id=context.vehicle.id,
            route_id=context.route.id,
            status=FuelOptimizationStatus.INFEASIBLE,
            stops=stops,
            total_fuel_consumed_gallons=_q4(total_consumed),
            total_fuel_purchased_gallons=_q4(total_purchased),
            total_fuel_cost=_money(total_cost_precise),
            total_detour_distance_meters=_q2(total_detour_distance),
            total_detour_time_seconds=total_detour_time,
            number_of_stops=len(stops),
            remaining_fuel_gallons=_q4(remaining_fuel),
            reached_stations=reached_stations,
            failure=failure,
            debug_trace=final_trace,
        )

    def _build_failure(
        self,
        context: FuelOptimizationContext,
        *,
        failure_reason: FuelOptimizationFailureReason,
        current_offset: Decimal,
        current_fuel: Decimal,
        current_station: FuelStationCandidate | None,
    ) -> FuelOptimizationFailure:
        reserve = context.constraints.reserve_gallons
        unreachable_stations: list[FuelOptimizationFailureTarget] = []
        for station in context.stations:
            if (
                not current_offset
                < station.route_offset_meters
                <= context.route.total_distance_meters
            ):
                continue
            fuel_required = self._fuel_to_station(context, current_offset, station)
            projected = current_fuel - fuel_required
            if projected >= reserve:
                continue
            unreachable_stations.append(
                FuelOptimizationFailureTarget(
                    kind="station",
                    station_id=station.station_id,
                    name=station.name or f"Station {station.station_id}",
                    route_offset_meters=_q4(station.route_offset_meters),
                    latitude=station.latitude,
                    longitude=station.longitude,
                    fuel_required_gallons=_q4(fuel_required),
                    available_fuel_gallons=_q4(current_fuel),
                    reserve_gallons=_q4(reserve),
                    projected_arrival_fuel_gallons=_q4(projected),
                    deficit_gallons=_q4_deficit(max(ZERO, reserve - projected)),
                )
            )
        unreachable_stations.sort(
            key=lambda target: (target.route_offset_meters, str(target.station_id))
        )

        destination_fuel_required = self._fuel_between(
            context, current_offset, context.route.total_distance_meters, ZERO
        )
        destination_projected = current_fuel - destination_fuel_required
        destination = None
        if destination_projected < reserve:
            longitude, latitude = context.route.geometry_coordinates[-1]
            destination = FuelOptimizationFailureTarget(
                kind="destination",
                station_id=None,
                name="Destination",
                route_offset_meters=_q4(context.route.total_distance_meters),
                latitude=Decimal(str(latitude)),
                longitude=Decimal(str(longitude)),
                fuel_required_gallons=_q4(destination_fuel_required),
                available_fuel_gallons=_q4(current_fuel),
                reserve_gallons=_q4(reserve),
                projected_arrival_fuel_gallons=_q4(destination_projected),
                deficit_gallons=_q4_deficit(max(ZERO, reserve - destination_projected)),
            )

        if failure_reason is FuelOptimizationFailureReason.INITIAL_FUEL_BELOW_RESERVE:
            longitude, latitude = context.route.geometry_coordinates[0]
            primary_target = FuelOptimizationFailureTarget(
                kind="start",
                station_id=None,
                name="Start",
                route_offset_meters=ZERO,
                latitude=Decimal(str(latitude)),
                longitude=Decimal(str(longitude)),
                fuel_required_gallons=ZERO,
                available_fuel_gallons=_q4(current_fuel),
                reserve_gallons=_q4(reserve),
                projected_arrival_fuel_gallons=_q4(current_fuel),
                deficit_gallons=_q4_deficit(max(ZERO, reserve - current_fuel)),
            )
        elif unreachable_stations:
            primary_target = unreachable_stations[0]
        elif destination is not None:
            primary_target = destination
        else:
            # All infeasible branches must have at least one unreachable target.
            raise RuntimeError("Infeasible optimization has no unreachable target")

        return FuelOptimizationFailure(
            reason=failure_reason,
            stopped_at_route_offset_meters=_q4(current_offset),
            last_reachable_station_id=(
                current_station.station_id if current_station is not None else None
            ),
            last_reachable_route_offset_meters=_q4(current_offset),
            available_fuel_gallons=_q4(current_fuel),
            reserve_gallons=_q4(reserve),
            primary_target=primary_target,
            unreachable_stations=unreachable_stations,
            destination=destination,
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


def _rank_alternatives(
    alternatives: list[StationAlternative],
) -> tuple[list[StationAlternative], int]:
    """Order alternatives by how much they need explaining and cap the list.

    Stations cheaper by sticker price come first (the user's natural question
    is "why not this one?"), those within reach before those that were not,
    then everything else by effective price.
    """

    def sort_key(item: StationAlternative) -> tuple[int, Decimal, Decimal]:
        if item.cheaper_by_sticker:
            group = 1 if item.outcome == "not_reachable" else 0
            return (group, item.fuel_price_per_gallon, item.route_offset_meters)
        effective = item.effective_price_per_gallon
        return (
            2 if effective is not None else 3,
            effective if effective is not None else ZERO,
            item.route_offset_meters,
        )

    return sorted(alternatives, key=sort_key), 0


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _q4(value: Decimal) -> Decimal:
    return value.quantize(FUEL_QUANT, rounding=ROUND_HALF_UP)


def _q4_ceil(value: Decimal) -> Decimal:
    return value.quantize(FUEL_QUANT, rounding=ROUND_CEILING)


def _q4_deficit(value: Decimal) -> Decimal:
    rounded = _q4(value)
    if value > ZERO and rounded == ZERO:
        return FUEL_QUANT
    return rounded


def _q2(value: Decimal) -> Decimal:
    return value.quantize(DISTANCE_QUANT, rounding=ROUND_HALF_UP)
