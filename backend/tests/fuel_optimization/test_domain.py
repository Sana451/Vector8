from __future__ import annotations

import uuid
from dataclasses import replace
from decimal import Decimal

import pytest

from app.fuel_optimization.domain import (
    ConstantMpgFuelConsumptionModel,
    Detour,
    EconomicStationCostModel,
    FuelOptimizationAlgorithm,
    FuelOptimizationConstraints,
    FuelOptimizationContext,
    FuelOptimizationFailureReason,
    FuelOptimizationStatus,
    FuelStationCandidate,
    GreedyFuelOptimizationStrategy,
    InvalidFuelOptimizationInputError,
    Route,
    StopEconomics,
    Vehicle,
)


class DummyDetourCalculator:
    def calculate(self, distance_from_route_meters: Decimal) -> Detour:
        return Detour(distance_meters=distance_from_route_meters, time_seconds=60)


def build_vehicle(*, usable: str = "142.5", mpg: str = "10") -> Vehicle:
    # usable is automatically calculated as 95% of tank capacity (150 * 0.95 = 142.5)
    # reserve is handled via FuelOptimizationConstraints, not in Vehicle
    return Vehicle(
        id=uuid.uuid4(),
        name="Truck 001",
        unit_number="TRK-001",
        vehicle_type="tractor",
        fuel_type="truck_diesel",
        tank_capacity_gallons=Decimal("150"),
        usable_tank_capacity_gallons=Decimal(usable),
        consumption_mpg=Decimal(mpg),
    )


def build_route(*, distance_meters: str = "160934") -> Route:
    return Route(
        id=uuid.uuid4(),
        total_distance_meters=Decimal(distance_meters),
        duration_seconds=3600,
        geometry_coordinates=[(-97.0, 40.0), (-96.0, 40.0)],
    )


def build_station(
    *,
    miles_from_start: str,
    price: str,
    detour_meters: str = "0",
    detour_seconds: int = 60,
    station_id: uuid.UUID | None = None,
) -> FuelStationCandidate:
    route_offset_meters = Decimal(miles_from_start) * Decimal("1609.344")
    return FuelStationCandidate(
        station_id=station_id or uuid.uuid4(),
        route_offset_meters=route_offset_meters,
        distance_from_route_meters=Decimal(detour_meters) / Decimal("2"),
        excursion_distance_meters=Decimal(detour_meters) / Decimal("2"),
        latitude=Decimal("40.0"),
        longitude=Decimal("-97.0"),
        fuel_type="truck_diesel",
        fuel_price_per_gallon=Decimal(price),
        truck_accessible=True,
        detour=Detour(
            distance_meters=Decimal(detour_meters), time_seconds=detour_seconds
        ),
    )


def build_context(
    *,
    initial_fuel: str,
    route_distance_miles: str,
    stations: list[FuelStationCandidate],
    reserve: str = "20",
    usable: str = "142.5",
    mpg: str = "10",
    min_refuel: str | None = None,
    economics: StopEconomics | None = None,
) -> FuelOptimizationContext:
    vehicle = build_vehicle(usable=usable, mpg=mpg)
    route = build_route(
        distance_meters=str(Decimal(route_distance_miles) * Decimal("1609.344"))
    )
    return FuelOptimizationContext(
        route=route,
        vehicle=vehicle,
        initial_fuel_gallons=Decimal(initial_fuel),
        stations=stations,
        algorithm=FuelOptimizationAlgorithm.GREEDY,
        constraints=FuelOptimizationConstraints(
            reserve_gallons=Decimal(reserve),
            min_refuel_gallons=Decimal(min_refuel) if min_refuel is not None else None,
        ),
        consumption_model=ConstantMpgFuelConsumptionModel(),
        detour_calculator=DummyDetourCalculator(),
        stop_economics=economics or StopEconomics(),
    )


def _vehicle_kwargs(**overrides):
    kwargs = {
        "id": uuid.uuid4(),
        "name": "Truck 001",
        "unit_number": "TRK-001",
        "vehicle_type": "tractor",
        "fuel_type": "truck_diesel",
        "tank_capacity_gallons": Decimal("10"),
        "usable_tank_capacity_gallons": Decimal("9.5"),
        "consumption_mpg": Decimal("7"),
    }
    kwargs.update(overrides)
    return kwargs


def test_vehicle_validates_fuel_invariants() -> None:
    # Test that usable_tank_capacity_gallons cannot exceed tank_capacity_gallons
    with pytest.raises(InvalidFuelOptimizationInputError):
        Vehicle(**_vehicle_kwargs(usable_tank_capacity_gallons=Decimal("11")))

    # Test that consumption_mpg must be positive
    with pytest.raises(InvalidFuelOptimizationInputError):
        Vehicle(**_vehicle_kwargs(consumption_mpg=Decimal("0")))


def test_constant_mpg_consumption_model_keeps_decimal_precision() -> None:
    vehicle = build_vehicle(mpg="10")
    model = ConstantMpgFuelConsumptionModel()
    result = model.fuel_required(Decimal("100"), vehicle)
    assert result == Decimal("10")


def test_greedy_returns_success_without_stops_when_destination_reachable() -> None:
    context = build_context(initial_fuel="50", route_distance_miles="200", stations=[])
    plan = GreedyFuelOptimizationStrategy().optimize(context)
    assert plan.status == FuelOptimizationStatus.SUCCESS
    assert plan.stops == []
    assert plan.number_of_stops == 0


def test_greedy_refuels_at_reachable_station_when_initial_fuel_below_reserve() -> None:
    station = build_station(miles_from_start="5", price="5.0000")
    context = build_context(
        initial_fuel="10",
        route_distance_miles="200",
        stations=[station],
        reserve="20",
        mpg="10",
    )
    plan = GreedyFuelOptimizationStrategy().optimize(context)
    assert plan.status == FuelOptimizationStatus.SUCCESS
    assert plan.number_of_stops == 1
    assert plan.stops[0].station_id == station.station_id
    assert plan.stops[0].fuel_before_gallons == Decimal("9.5000")


def test_greedy_is_infeasible_when_initial_fuel_below_reserve_and_no_station_reachable() -> (
    None
):
    context = build_context(
        initial_fuel="10", route_distance_miles="200", stations=[], reserve="20"
    )
    plan = GreedyFuelOptimizationStrategy().optimize(context)
    assert plan.status == FuelOptimizationStatus.INFEASIBLE
    assert plan.failure is not None


def test_infeasible_reports_all_unreachable_stations_and_nearest_target() -> None:
    nearest = build_station(miles_from_start="80", price="6.0000")
    farther = build_station(miles_from_start="100", price="5.9000")
    context = build_context(
        initial_fuel="25",
        route_distance_miles="300",
        stations=[farther, nearest],
        reserve="20",
        mpg="10",
    )

    plan = GreedyFuelOptimizationStrategy().optimize(context)

    assert plan.status == FuelOptimizationStatus.INFEASIBLE
    assert plan.failure is not None
    assert plan.failure.reason == FuelOptimizationFailureReason.NO_REACHABLE_STATION
    assert plan.failure.primary_target.station_id == nearest.station_id
    assert [station.station_id for station in plan.failure.unreachable_stations] == [
        nearest.station_id,
        farther.station_id,
    ]
    assert plan.failure.primary_target.fuel_required_gallons == Decimal("8.0000")
    assert plan.failure.primary_target.available_fuel_gallons == Decimal("25.0000")
    assert plan.failure.primary_target.reserve_gallons == Decimal("20.0000")
    assert plan.failure.primary_target.deficit_gallons == Decimal("3.0000")
    assert plan.failure.destination is not None
    assert plan.failure.destination.kind == "destination"


def test_infeasible_preserves_reached_station_and_planned_refuel() -> None:
    station = build_station(miles_from_start="150", price="5.5000")
    context = build_context(
        initial_fuel="60",
        route_distance_miles="1700",
        stations=[station],
        reserve="20",
        mpg="10",
    )

    plan = GreedyFuelOptimizationStrategy().optimize(context)

    assert plan.status == FuelOptimizationStatus.INFEASIBLE
    assert plan.number_of_stops == 1
    assert plan.stops[0].station_id == station.station_id
    assert plan.reached_stations[0].station_id == station.station_id
    assert plan.failure is not None
    assert plan.failure.reason == FuelOptimizationFailureReason.DESTINATION_UNREACHABLE
    assert plan.failure.last_reachable_station_id == station.station_id
    assert plan.failure.primary_target.kind == "destination"
    assert plan.failure.primary_target.deficit_gallons > Decimal("0")


def test_greedy_makes_one_necessary_stop() -> None:
    station = build_station(miles_from_start="300", price="6.0000")
    context = build_context(
        initial_fuel="60",
        route_distance_miles="600",
        stations=[station],
        reserve="20",
        mpg="10",
    )
    plan = GreedyFuelOptimizationStrategy().optimize(context)
    assert plan.status == FuelOptimizationStatus.SUCCESS
    assert plan.number_of_stops == 1
    assert plan.stops[0].station_id == station.station_id
    assert (
        plan.stops[0].fuel_after_gallons <= context.vehicle.usable_tank_capacity_gallons
    )


def test_greedy_buys_only_enough_to_reach_cheaper_station_ahead() -> None:
    expensive = build_station(miles_from_start="200", price="6.0000")
    cheaper = build_station(miles_from_start="350", price="5.5000")
    context = build_context(
        initial_fuel="50",
        route_distance_miles="700",
        stations=[expensive, cheaper],
        reserve="20",
        mpg="10",
    )
    plan = GreedyFuelOptimizationStrategy().optimize(context)
    assert plan.status == FuelOptimizationStatus.SUCCESS
    assert plan.number_of_stops >= 1
    first_stop = plan.stops[0]
    assert first_stop.station_id == expensive.station_id
    assert first_stop.fuel_added_gallons < Decimal("145")
    assert first_stop.fuel_after_gallons <= context.vehicle.usable_tank_capacity_gallons


def test_greedy_skips_station_when_min_refuel_cannot_fit_in_tank() -> None:
    nearly_full_station = build_station(miles_from_start="10", price="5.0000")
    context = build_context(
        initial_fuel="100",
        route_distance_miles="500",
        stations=[nearly_full_station],
        reserve="20",
        mpg="10",
        min_refuel="50",
    )
    plan = GreedyFuelOptimizationStrategy().optimize(context)
    assert plan.status == FuelOptimizationStatus.SUCCESS
    assert plan.number_of_stops == 0


def test_greedy_rounds_required_refuel_up_to_fuel_precision() -> None:
    current = build_station(miles_from_start="200", price="6.0000")
    cheaper = build_station(miles_from_start="350.00001", price="5.5000")
    context = build_context(
        initial_fuel="50",
        route_distance_miles="700",
        stations=[current, cheaper],
        reserve="20",
        mpg="10",
    )

    plan = GreedyFuelOptimizationStrategy().optimize(context)

    assert plan.status == FuelOptimizationStatus.SUCCESS
    first_stop = plan.stops[0]
    assert first_stop.station_id == current.station_id
    assert first_stop.fuel_after_gallons == Decimal("35.0001")
    refuel_decision = next(
        step for step in plan.debug_trace if step["event"] == "refuel_decision"
    )
    assert (
        first_stop.fuel_after_gallons >= refuel_decision["desired_fuel_after_gallons"]
    )


def test_greedy_respects_detour_in_reachability() -> None:
    detour_heavy_station = build_station(
        miles_from_start="250",
        price="5.9000",
        detour_meters="32186.88",
    )
    context = build_context(
        initial_fuel="45",
        route_distance_miles="500",
        stations=[detour_heavy_station],
        reserve="20",
        mpg="10",
    )
    plan = GreedyFuelOptimizationStrategy().optimize(context)
    assert plan.status == FuelOptimizationStatus.INFEASIBLE


def test_greedy_is_deterministic_for_same_offset_candidates() -> None:
    station_a = build_station(
        miles_from_start="300",
        price="5.9000",
        station_id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
    )
    station_b = build_station(
        miles_from_start="300",
        price="5.8000",
        station_id=uuid.UUID("00000000-0000-0000-0000-000000000011"),
    )
    context = build_context(
        initial_fuel="40",
        route_distance_miles="900",
        stations=[station_b, station_a],
        reserve="20",
        mpg="10",
    )
    strategy = GreedyFuelOptimizationStrategy()
    first = strategy.optimize(context)
    second = strategy.optimize(context)
    assert first == second


def test_effective_price_collapses_to_raw_price_without_detour_or_economics() -> None:
    station = build_station(miles_from_start="50", price="4.0000")
    model = EconomicStationCostModel(StopEconomics())
    assert model.effective_price_per_gallon(station, Decimal("100")) == Decimal(
        "4.0000"
    )


def test_effective_price_penalizes_detour_fuel() -> None:
    station = build_station(
        miles_from_start="50", price="3.9800", detour_meters="40000"
    )
    model = EconomicStationCostModel(StopEconomics())
    raw = station.fuel_price_per_gallon
    effective = model.effective_price_per_gallon(
        station, Decimal("115"), Decimal("2.485")
    )
    assert effective is not None
    assert effective > raw


def test_effective_price_is_none_when_detour_swallows_the_purchase() -> None:
    station = build_station(miles_from_start="50", price="4.0000")
    model = EconomicStationCostModel(StopEconomics())
    assert model.effective_price_per_gallon(station, Decimal("2"), Decimal("3")) is None
    assert model.effective_price_per_gallon(station, Decimal("0")) is None


def test_greedy_prefers_pricier_station_without_detour_over_cheaper_with_detour() -> (
    None
):
    # Neutral economics (the defaults): detour *fuel* is still priced in, so the
    # $0.02 discount does not pay for a 40 km round trip.
    on_route = build_station(
        miles_from_start="50",
        price="4.0000",
        station_id=uuid.UUID("00000000-0000-0000-0000-0000000000a1"),
    )
    far_off_route = build_station(
        miles_from_start="51",
        price="3.9800",
        detour_meters="40000",
        station_id=uuid.UUID("00000000-0000-0000-0000-0000000000a2"),
    )
    context = build_context(
        initial_fuel="35",
        route_distance_miles="200",
        stations=[on_route, far_off_route],
        reserve="20",
        mpg="10",
    )
    plan = GreedyFuelOptimizationStrategy().optimize(context)
    assert plan.reached_stations[0].station_id == on_route.station_id


def test_greedy_still_picks_cheaper_station_when_detour_is_small() -> None:
    on_route = build_station(
        miles_from_start="50",
        price="4.0000",
        station_id=uuid.UUID("00000000-0000-0000-0000-0000000000b1"),
    )
    slightly_off_route = build_station(
        miles_from_start="51",
        price="3.5000",
        detour_meters="1000",
        station_id=uuid.UUID("00000000-0000-0000-0000-0000000000b2"),
    )
    context = build_context(
        initial_fuel="35",
        route_distance_miles="200",
        stations=[on_route, slightly_off_route],
        reserve="20",
        mpg="10",
    )
    plan = GreedyFuelOptimizationStrategy().optimize(context)
    assert plan.reached_stations[0].station_id == slightly_off_route.station_id


def _two_station_lookahead_context(economics: StopEconomics) -> FuelOptimizationContext:
    near = build_station(
        miles_from_start="10",
        price="4.0000",
        station_id=uuid.UUID("00000000-0000-0000-0000-0000000000c1"),
    )
    marginally_cheaper = build_station(
        miles_from_start="200",
        price="3.9800",
        station_id=uuid.UUID("00000000-0000-0000-0000-0000000000c2"),
    )
    return build_context(
        initial_fuel="25",
        route_distance_miles="400",
        stations=[near, marginally_cheaper],
        reserve="20",
        mpg="10",
        economics=economics,
    )


def test_marginally_cheaper_station_is_used_when_stops_are_free() -> None:
    plan = GreedyFuelOptimizationStrategy().optimize(
        _two_station_lookahead_context(StopEconomics())
    )
    assert plan.status == FuelOptimizationStatus.SUCCESS
    assert plan.number_of_stops == 2


def test_dwell_and_downtime_cost_suppress_a_marginally_cheaper_extra_stop() -> None:
    economics = StopEconomics(
        downtime_cost_per_hour=Decimal("75"), dwell_minutes=Decimal("30")
    )
    plan = GreedyFuelOptimizationStrategy().optimize(
        _two_station_lookahead_context(economics)
    )
    assert plan.status == FuelOptimizationStatus.SUCCESS
    assert plan.number_of_stops == 1


def test_mandatory_next_stop_is_not_penalized_by_stop_overhead() -> None:
    # A full tank (142.5 gal / 10 mpg = 1425 mi) cannot finish a 3000 mi route,
    # so the stop ahead is unavoidable and its overhead must not be charged.
    near = build_station(
        miles_from_start="10",
        price="4.0000",
        station_id=uuid.UUID("00000000-0000-0000-0000-0000000000d1"),
    )
    ahead = build_station(
        miles_from_start="1000",
        price="3.9800",
        station_id=uuid.UUID("00000000-0000-0000-0000-0000000000d2"),
    )
    economics = StopEconomics(
        downtime_cost_per_hour=Decimal("500"), dwell_minutes=Decimal("60")
    )
    context = build_context(
        initial_fuel="25",
        route_distance_miles="3000",
        stations=[near, ahead],
        reserve="20",
        mpg="10",
        economics=economics,
    )
    plan = GreedyFuelOptimizationStrategy().optimize(context)
    reached = [station.station_id for station in plan.reached_stations]
    assert ahead.station_id in reached


def test_dwell_minutes_have_no_effect_while_downtime_cost_is_zero() -> None:
    # Dwell time is converted to money through the driver cost, so configuring
    # it alone silently does nothing. Guards against a misleading .env setup.
    station = build_station(miles_from_start="50", price="4.0000")
    without = EconomicStationCostModel(StopEconomics())
    dwell_only = EconomicStationCostModel(StopEconomics(dwell_minutes=Decimal("30")))

    assert (
        dwell_only.stop_time_cost(station)
        == without.stop_time_cost(station)
        == Decimal("0")
    )
    assert dwell_only.effective_price_per_gallon(
        station, Decimal("100")
    ) == without.effective_price_per_gallon(station, Decimal("100"))


def test_dwell_minutes_apply_once_downtime_cost_is_set() -> None:
    station = build_station(miles_from_start="50", price="4.0000", detour_seconds=0)
    model = EconomicStationCostModel(
        StopEconomics(downtime_cost_per_hour=Decimal("75"), dwell_minutes=Decimal("30"))
    )
    # Half an hour of a $75/h truck.
    assert model.stop_time_cost(station) == Decimal("37.5")


def test_stop_economics_rejects_negative_values() -> None:
    with pytest.raises(InvalidFuelOptimizationInputError):
        StopEconomics(downtime_cost_per_hour=Decimal("-1"))
    with pytest.raises(InvalidFuelOptimizationInputError):
        StopEconomics(dwell_minutes=Decimal("-1"))
    with pytest.raises(InvalidFuelOptimizationInputError):
        StopEconomics(fixed_stop_cost=Decimal("-1"))


def test_neutral_stop_economics_is_reported_as_neutral() -> None:
    assert StopEconomics().is_neutral is True
    assert StopEconomics(dwell_minutes=Decimal("30")).is_neutral is False


def _selection_context() -> tuple[FuelOptimizationContext, uuid.UUID, uuid.UUID]:
    on_route = build_station(
        miles_from_start="50",
        price="4.0000",
        station_id=uuid.UUID("00000000-0000-0000-0000-0000000000d1"),
    )
    far_off_route = build_station(
        miles_from_start="51",
        price="3.9800",
        detour_meters="40000",
        station_id=uuid.UUID("00000000-0000-0000-0000-0000000000d2"),
    )
    context = build_context(
        initial_fuel="35",
        route_distance_miles="200",
        stations=[on_route, far_off_route],
        reserve="20",
        mpg="10",
    )
    return context, on_route.station_id, far_off_route.station_id


def test_stop_selection_explains_why_pricier_station_won() -> None:
    context, chosen_id, rejected_id = _selection_context()
    plan = GreedyFuelOptimizationStrategy().optimize(context)

    stop = plan.stops[0]
    assert stop.station_id == chosen_id
    selection = stop.selection
    assert selection is not None
    assert selection.rule == "lowest_effective_price"
    assert selection.sticker_price_per_gallon == Decimal("4.0000")
    assert selection.effective_price_per_gallon is not None
    alternative = selection.alternatives[0]
    assert alternative.station_id == rejected_id
    assert alternative.cheaper_by_sticker is True
    assert alternative.outcome == "higher_effective_price"
    assert alternative.delta_vs_chosen_per_gallon is not None
    assert alternative.delta_vs_chosen_per_gallon > 0


def test_selection_premium_reconciles_with_cost_breakdown() -> None:
    economics = StopEconomics(
        downtime_cost_per_hour=Decimal("60"), dwell_minutes=Decimal("30")
    )
    context, _, _ = _selection_context()
    context = replace(context, stop_economics=economics)
    selection = GreedyFuelOptimizationStrategy().optimize(context).stops[0].selection
    assert selection is not None
    assert selection.premium_per_gallon is not None
    assert selection.delivered_gallons is not None
    total = selection.detour_fuel_cost + selection.time_cost + selection.fixed_stop_cost
    reconstructed = selection.premium_per_gallon * selection.delivered_gallons
    assert abs(reconstructed - total) < Decimal("0.05")


def test_cheaper_ahead_stop_records_savings_and_lookahead() -> None:
    plan = GreedyFuelOptimizationStrategy().optimize(
        _two_station_lookahead_context(StopEconomics())
    )
    first, second = plan.stops
    assert first.lookahead is not None
    assert first.lookahead.rule == "cheaper_ahead_pays_off"
    assert second.selection is not None
    assert second.selection.rule == "cheaper_ahead_pays_off"
    assert second.selection.estimated_savings is not None
    assert second.selection.effective_price_per_gallon is None


def test_rejected_cheaper_ahead_is_reported_in_lookahead() -> None:
    economics = StopEconomics(
        downtime_cost_per_hour=Decimal("75"), dwell_minutes=Decimal("30")
    )
    plan = GreedyFuelOptimizationStrategy().optimize(
        _two_station_lookahead_context(economics)
    )
    lookahead = plan.stops[0].lookahead
    assert lookahead is not None
    assert lookahead.rule == "cheaper_ahead_rejected"
    assert lookahead.stop_overhead_cost is not None
    assert lookahead.estimated_savings is not None
    assert lookahead.stop_overhead_cost > lookahead.estimated_savings


def test_selection_lists_all_alternatives() -> None:
    stations = [
        build_station(
            miles_from_start=str(40 + index),
            price=f"4.{index:02d}00",
            station_id=uuid.UUID(f"00000000-0000-0000-0000-0000000001{index:02d}"),
        )
        for index in range(9)
    ]
    context = build_context(
        initial_fuel="35",
        route_distance_miles="200",
        stations=stations,
        reserve="20",
        mpg="10",
    )
    selection = GreedyFuelOptimizationStrategy().optimize(context).stops[0].selection
    assert selection is not None
    assert len(selection.alternatives) == 8
    assert selection.alternatives_omitted_count == 0


def test_cheaper_ahead_selection_lists_other_stations_in_reach() -> None:
    near = build_station(
        miles_from_start="10",
        price="4.0000",
        station_id=uuid.UUID("00000000-0000-0000-0000-0000000000e1"),
    )
    chosen = build_station(
        miles_from_start="200",
        price="3.9000",
        station_id=uuid.UUID("00000000-0000-0000-0000-0000000000e2"),
    )
    further_cheaper = build_station(
        miles_from_start="250",
        price="3.8000",
        station_id=uuid.UUID("00000000-0000-0000-0000-0000000000e3"),
    )
    pricier = build_station(
        miles_from_start="300",
        price="4.2000",
        station_id=uuid.UUID("00000000-0000-0000-0000-0000000000e4"),
    )
    context = build_context(
        initial_fuel="25",
        route_distance_miles="400",
        stations=[near, chosen, further_cheaper, pricier],
        reserve="20",
        mpg="10",
    )
    plan = GreedyFuelOptimizationStrategy().optimize(context)
    selection = next(
        stop.selection for stop in plan.stops if stop.station_id == chosen.station_id
    )
    assert selection is not None
    assert selection.rule == "cheaper_ahead_pays_off"
    outcomes = {a.station_id: a.outcome for a in selection.alternatives}
    assert outcomes[further_cheaper.station_id] == "nearer_cheaper_station_chosen"
    assert outcomes[pricier.station_id] == "not_cheaper_than_previous"
