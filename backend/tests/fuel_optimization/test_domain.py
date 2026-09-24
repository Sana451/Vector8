from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.fuel_optimization.domain import (
    ConstantMpgFuelConsumptionModel,
    Detour,
    FuelOptimizationAlgorithm,
    FuelOptimizationConstraints,
    FuelOptimizationContext,
    FuelOptimizationStatus,
    FuelStationCandidate,
    GreedyFuelOptimizationStrategy,
    InvalidFuelOptimizationInputError,
    Route,
    Vehicle,
    VehicleFuelProfile,
)


class DummyDetourCalculator:
    def calculate(self, distance_from_route_meters: Decimal) -> Detour:
        return Detour(distance_meters=distance_from_route_meters, time_seconds=60)


def build_vehicle(
    *, reserve: str = "20", usable: str = "145", mpg: str = "10"
) -> Vehicle:
    profile = VehicleFuelProfile(
        id=uuid.uuid4(),
        fuel_type="truck_diesel",
        tank_capacity_gallons=Decimal("150"),
        usable_tank_capacity_gallons=Decimal(usable),
        consumption_mpg=Decimal(mpg),
        reserve_gallons=Decimal(reserve),
    )
    return Vehicle(
        id=uuid.uuid4(),
        name="Truck 001",
        unit_number="TRK-001",
        vehicle_type="tractor",
        fuel_profile=profile,
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
        detour=Detour(distance_meters=Decimal(detour_meters), time_seconds=60),
    )


def build_context(
    *,
    initial_fuel: str,
    route_distance_miles: str,
    stations: list[FuelStationCandidate],
    reserve: str = "20",
    usable: str = "145",
    mpg: str = "10",
) -> FuelOptimizationContext:
    vehicle = build_vehicle(reserve=reserve, usable=usable, mpg=mpg)
    route = build_route(
        distance_meters=str(Decimal(route_distance_miles) * Decimal("1609.344"))
    )
    return FuelOptimizationContext(
        route=route,
        vehicle=vehicle,
        initial_fuel_gallons=Decimal(initial_fuel),
        stations=stations,
        algorithm=FuelOptimizationAlgorithm.GREEDY,
        constraints=FuelOptimizationConstraints(reserve_gallons=Decimal(reserve)),
        consumption_model=ConstantMpgFuelConsumptionModel(),
        detour_calculator=DummyDetourCalculator(),
    )


def test_vehicle_fuel_profile_validates_invariants() -> None:
    with pytest.raises(InvalidFuelOptimizationInputError):
        VehicleFuelProfile(
            id=uuid.uuid4(),
            fuel_type="truck_diesel",
            tank_capacity_gallons=Decimal("10"),
            usable_tank_capacity_gallons=Decimal("11"),
            consumption_mpg=Decimal("7"),
            reserve_gallons=Decimal("1"),
        )

    with pytest.raises(InvalidFuelOptimizationInputError):
        VehicleFuelProfile(
            id=uuid.uuid4(),
            fuel_type="truck_diesel",
            tank_capacity_gallons=Decimal("10"),
            usable_tank_capacity_gallons=Decimal("10"),
            consumption_mpg=Decimal("7"),
            reserve_gallons=Decimal("10"),
        )


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


def test_greedy_returns_infeasible_when_initial_fuel_below_reserve() -> None:
    context = build_context(initial_fuel="10", route_distance_miles="200", stations=[])
    plan = GreedyFuelOptimizationStrategy().optimize(context)
    assert plan.status == FuelOptimizationStatus.INFEASIBLE


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
        plan.stops[0].fuel_after_gallons
        <= context.vehicle.fuel_profile.usable_tank_capacity_gallons
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
    assert (
        first_stop.fuel_after_gallons
        <= context.vehicle.fuel_profile.usable_tank_capacity_gallons
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
