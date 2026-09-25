from __future__ import annotations

import uuid
from decimal import Decimal

from sqlmodel import Session, select

from app.fuel_optimization.domain import FuelOptimizationPlan
from app.fuel_optimization.models import FuelOptimizationRun, FuelOptimizationStop
from app.routing.models import RouteCalculation


class FuelOptimizationRunRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        route_id: uuid.UUID,
        vehicle_id: uuid.UUID,
        initial_fuel_gallons: Decimal,
        plan: FuelOptimizationPlan,
    ) -> FuelOptimizationRun:
        run = FuelOptimizationRun(
            route_id=route_id,
            vehicle_id=vehicle_id,
            algorithm=plan.algorithm,
            algorithm_version=plan.algorithm_version,
            status=plan.status,
            initial_fuel_gallons=initial_fuel_gallons,
            total_fuel_consumed_gallons=plan.total_fuel_consumed_gallons,
            total_fuel_purchased_gallons=plan.total_fuel_purchased_gallons,
            total_fuel_cost=plan.total_fuel_cost,
            total_detour_distance_meters=plan.total_detour_distance_meters,
            total_detour_time_seconds=plan.total_detour_time_seconds,
            number_of_stops=plan.number_of_stops,
            remaining_fuel_gallons=plan.remaining_fuel_gallons,
        )
        self.session.add(run)
        self.session.flush()
        for stop in plan.stops:
            self.session.add(
                FuelOptimizationStop(
                    optimization_run_id=run.id,
                    sequence=stop.sequence,
                    station_id=stop.station_id,
                    route_offset_meters=stop.route_offset_meters,
                    fuel_before_gallons=stop.fuel_before_gallons,
                    fuel_added_gallons=stop.fuel_added_gallons,
                    fuel_after_gallons=stop.fuel_after_gallons,
                    fuel_price_per_gallon=stop.fuel_price_per_gallon,
                    fuel_cost=stop.fuel_cost,
                    detour_distance_meters=stop.detour_distance_meters,
                    detour_time_seconds=stop.detour_time_seconds,
                )
            )
        self.session.commit()
        self.session.refresh(run)
        return run


class RouteCalculationQueryRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, route_id: uuid.UUID) -> RouteCalculation | None:
        statement = select(RouteCalculation).where(RouteCalculation.id == route_id)
        return self.session.exec(statement).first()
