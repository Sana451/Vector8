from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from enum import Enum
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.fleet.models import VehicleFuelType
from app.fleet.repository import VehicleRepository
from app.fuel_optimization.domain import (
    ConstantMpgFuelConsumptionModel,
    Detour,
    DetourCalculator,
    FuelOptimizationAlgorithm,
    FuelOptimizationConstraints,
    FuelOptimizationContext,
    FuelOptimizationEngine,
    FuelOptimizationPlan,
    FuelOptimizationStatus,
    FuelOptimizationStrategyRegistry,
    FuelStationCandidate,
    GreedyFuelOptimizationStrategy,
    InvalidFuelOptimizationInputError,
    Route,
    Vehicle,
    VehicleFuelProfile,
)
from app.fuel_optimization.exceptions import (
    FuelProfileNotFoundError,
    RouteNotFoundError,
    VehicleNotFoundError,
)
from app.fuel_optimization.repository import (
    FuelOptimizationRunRepository,
    RouteCalculationQueryRepository,
)
from app.fuel_optimization.schemas import (
    FuelOptimizationCalculateRequest,
    FuelOptimizationCalculateResponse,
    FuelOptimizationExplanationPublic,
    FuelOptimizationSkippedStationPointPublic,
    FuelOptimizationSkippedStationStatPublic,
    FuelOptimizationStopPublic,
    FuelOptimizationSummaryPublic,
)
from app.map.repository import FuelStationRepository
from app.providers.schemas import FuelStationData
from app.routing.schemas import CalculateRouteResponse

logger = get_logger(__name__)

APPROX_DETOUR_TIME_METERS_PER_SECOND = Decimal("13.4112")


@dataclass(frozen=True)
class CandidateBuildResult:
    candidates: list[FuelStationCandidate]
    audit: list[dict[str, Any]]
    metadata: dict[str, Any]


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


class ApproximateDetourCalculator:
    def calculate(self, distance_from_route_meters: Decimal) -> Detour:
        detour_distance = distance_from_route_meters * Decimal("2")
        time_seconds = int(
            (detour_distance / APPROX_DETOUR_TIME_METERS_PER_SECOND).to_integral_value()
        )
        return Detour(
            distance_meters=detour_distance,
            time_seconds=max(time_seconds, 0),
            is_approximation=True,
        )


class FuelStationCandidateBuilder:
    def __init__(
        self,
        fuel_station_repository: FuelStationRepository,
        detour_calculator: DetourCalculator,
    ):
        self.fuel_station_repository = fuel_station_repository
        self.detour_calculator = detour_calculator

    def build(
        self,
        *,
        route: Route,
        constraints: FuelOptimizationConstraints,
    ) -> CandidateBuildResult:
        default_search_radius_meters = settings.MAP_LAYER_RADIUS_METERS
        requested_max_detour_meters = constraints.max_allowed_detour_meters
        effective_search_radius_meters = default_search_radius_meters
        if requested_max_detour_meters is not None:
            effective_search_radius_meters = max(
                default_search_radius_meters,
                int(
                    requested_max_detour_meters.to_integral_value(
                        rounding=ROUND_CEILING
                    )
                ),
            )
        rows = self.fuel_station_repository.find_along_route(
            coordinates=route.geometry_coordinates,
            radius_meters=effective_search_radius_meters,
            limit=settings.MAP_LAYER_RESULT_LIMIT,
            provider="internal",
        )
        candidates_by_id: dict[uuid.UUID, FuelStationCandidate] = {}
        audit: list[dict[str, Any]] = []
        for row in rows:
            station = FuelStationData.model_validate(row.payload)
            lon, lat = station.location.coordinates
            fuel_type = self._normalize_fuel_type(station.fuel_type)
            truck_accessible = bool(
                row.medium_truck_accessible and row.large_truck_accessible
            )
            distance_from_route = Decimal(
                str(getattr(row, "distance_to_route_meters", 0.0))
            )
            detour = self.detour_calculator.calculate(distance_from_route)
            fraction = Decimal(str(getattr(row, "progress_along_route", 0.0)))
            route_offset = fraction * route.total_distance_meters
            audit_entry = {
                "station_id": row.id,
                "external_id": station.external_id,
                "name": station.name,
                "latitude": Decimal(str(lat)),
                "longitude": Decimal(str(lon)),
                "fuel_type_raw": station.fuel_type,
                "fuel_type_normalized": fuel_type,
                "diesel_price": Decimal(str(row.diesel_price))
                if row.diesel_price is not None
                else None,
                "medium_truck_accessible": row.medium_truck_accessible,
                "large_truck_accessible": row.large_truck_accessible,
                "truck_accessible": truck_accessible,
                "distance_from_route_meters": distance_from_route,
                "detour_distance_meters": detour.distance_meters,
                "detour_time_seconds": detour.time_seconds,
                "detour_is_approximation": detour.is_approximation,
                "progress_fraction": fraction,
                "route_offset_meters": route_offset,
                "included": False,
                "reason": None,
                "formula_route_offset": "route_offset_meters = progress_fraction * route_total_distance_meters",
                "formula_detour": "detour_distance_meters ≈ 2 * distance_from_route_meters",
            }
            if row.id in candidates_by_id:
                audit_entry["reason"] = "duplicate_station_id"
                audit.append(audit_entry)
                continue
            if fuel_type != VehicleFuelType.TRUCK_DIESEL.value:
                audit_entry["reason"] = "unsupported_fuel_type"
                audit.append(audit_entry)
                continue
            if row.diesel_price is None:
                audit_entry["reason"] = "missing_diesel_price"
                audit.append(audit_entry)
                continue
            if not truck_accessible:
                audit_entry["reason"] = "not_truck_accessible"
                audit.append(audit_entry)
                continue
            if (
                constraints.max_allowed_detour_meters is not None
                and detour.distance_meters > constraints.max_allowed_detour_meters
            ):
                audit_entry["reason"] = "detour_distance_limit_exceeded"
                audit_entry["max_allowed_detour_meters"] = (
                    constraints.max_allowed_detour_meters
                )
                audit.append(audit_entry)
                continue
            candidates_by_id[row.id] = FuelStationCandidate(
                station_id=row.id,
                route_offset_meters=route_offset,
                distance_from_route_meters=distance_from_route,
                excursion_distance_meters=distance_from_route,
                latitude=Decimal(str(lat)),
                longitude=Decimal(str(lon)),
                fuel_type=self._normalize_fuel_type(station.fuel_type),
                fuel_price_per_gallon=Decimal(str(row.diesel_price)),
                truck_accessible=truck_accessible,
                detour=detour,
            )
            audit_entry["included"] = True
            audit_entry["reason"] = "candidate_included"
            audit.append(audit_entry)
        return CandidateBuildResult(
            candidates=sorted(
                candidates_by_id.values(),
                key=lambda item: (item.route_offset_meters, str(item.station_id)),
            ),
            audit=audit,
            metadata={
                "default_search_radius_meters": default_search_radius_meters,
                "effective_search_radius_meters": effective_search_radius_meters,
                "requested_max_detour_meters": (
                    int(
                        requested_max_detour_meters.to_integral_value(
                            rounding=ROUND_CEILING
                        )
                    )
                    if requested_max_detour_meters is not None
                    else None
                ),
                "search_limit": settings.MAP_LAYER_RESULT_LIMIT,
                "rows_received_from_repository": len(rows),
                "candidate_count": len(candidates_by_id),
                "filter_sequence": [
                    "deduplicate_by_station_id",
                    "normalize_and_require_truck_diesel",
                    "require_non_null_diesel_price",
                    "require_medium_and_large_truck_access",
                    "apply_detour_distance_limit_if_present",
                    "sort_by_route_offset_then_station_id",
                ],
            },
        )

    @staticmethod
    def _normalize_fuel_type(value: str | None) -> str:
        if not value:
            return ""
        return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


class OptimizeFuelUseCase:
    def __init__(
        self,
        vehicle_repository: VehicleRepository,
        route_repository: RouteCalculationQueryRepository,
        fuel_station_repository: FuelStationRepository,
        run_repository: FuelOptimizationRunRepository,
    ):
        self.vehicle_repository = vehicle_repository
        self.route_repository = route_repository
        self.fuel_station_repository = fuel_station_repository
        self.run_repository = run_repository
        self.detour_calculator = ApproximateDetourCalculator()
        self.strategy_registry = FuelOptimizationStrategyRegistry(
            {FuelOptimizationAlgorithm.GREEDY: GreedyFuelOptimizationStrategy()}
        )
        self.engine = FuelOptimizationEngine(self.strategy_registry)

    def execute(
        self,
        request: FuelOptimizationCalculateRequest,
    ) -> FuelOptimizationCalculateResponse:
        debug: dict[str, Any] = {
            "request": self._serialize_debug(
                {
                    "route_id": request.route_id,
                    "vehicle_id": request.vehicle_id,
                    "algorithm": request.algorithm,
                    "initial_fuel_gallons": request.initial_fuel_gallons,
                    "constraints": (
                        request.constraints.model_dump()
                        if request.constraints is not None
                        else None
                    ),
                }
            ),
            "formulas": {
                "route_offset_meters": "route_offset_meters = progress_fraction * route_total_distance_meters",
                "detour_distance_meters": "detour_distance_meters ≈ 2 * distance_from_route_meters",
                "travel_distance_miles": "travel_distance_miles = (route_distance_meters + detour_distance_meters) * 0.000621371192237334",
                "fuel_required_gallons": "fuel_required_gallons = travel_distance_miles / consumption_mpg",
                "reachable": "reachable = current_fuel_gallons - fuel_required_gallons >= reserve_gallons",
                "fuel_added_gallons": "fuel_added_gallons = min(max(0, desired_fuel_after_gallons - current_fuel_gallons), usable_tank_capacity_gallons - current_fuel_gallons)",
                "fuel_cost": "fuel_cost = fuel_added_gallons * fuel_price_per_gallon",
            },
        }
        vehicle_row = self.vehicle_repository.get(request.vehicle_id)
        if vehicle_row is None:
            raise VehicleNotFoundError("Vehicle not found")
        fuel_profile_row = self.vehicle_repository.get_fuel_profile(
            vehicle_row.fuel_profile_id
        )
        if fuel_profile_row is None:
            raise FuelProfileNotFoundError("Vehicle fuel profile not found")
        route_row = self.route_repository.get(request.route_id)
        if route_row is None:
            raise RouteNotFoundError("Route not found")

        vehicle = Vehicle(
            id=vehicle_row.id,
            name=vehicle_row.name,
            unit_number=vehicle_row.unit_number,
            vehicle_type=_enum_value(vehicle_row.vehicle_type),
            routing_profile_id=vehicle_row.routing_profile_id,
            fuel_profile=VehicleFuelProfile(
                id=fuel_profile_row.id,
                fuel_type=_enum_value(fuel_profile_row.fuel_type),
                tank_capacity_gallons=fuel_profile_row.tank_capacity_gallons,
                usable_tank_capacity_gallons=fuel_profile_row.usable_tank_capacity_gallons,
                consumption_mpg=fuel_profile_row.consumption_mpg,
                reserve_gallons=fuel_profile_row.reserve_gallons,
                min_refuel_gallons=fuel_profile_row.min_refuel_gallons,
                max_refuel_gallons=fuel_profile_row.max_refuel_gallons,
            ),
        )
        route = self._build_route(route_row)
        constraints = FuelOptimizationConstraints(
            reserve_gallons=(
                request.constraints.reserve_gallons
                if request.constraints
                and request.constraints.reserve_gallons is not None
                else vehicle.fuel_profile.reserve_gallons
            ),
            max_allowed_detour_meters=(
                request.constraints.max_allowed_detour_meters
                if request.constraints
                else None
            ),
        )
        debug["vehicle"] = self._serialize_debug(
            {
                "id": vehicle.id,
                "name": vehicle.name,
                "unit_number": vehicle.unit_number,
                "vehicle_type": vehicle.vehicle_type,
                "routing_profile_id": vehicle.routing_profile_id,
            }
        )
        debug["fuel_profile"] = self._serialize_debug(
            {
                "id": vehicle.fuel_profile.id,
                "fuel_type": vehicle.fuel_profile.fuel_type,
                "tank_capacity_gallons": vehicle.fuel_profile.tank_capacity_gallons,
                "usable_tank_capacity_gallons": vehicle.fuel_profile.usable_tank_capacity_gallons,
                "consumption_mpg": vehicle.fuel_profile.consumption_mpg,
                "reserve_gallons": vehicle.fuel_profile.reserve_gallons,
                "min_refuel_gallons": vehicle.fuel_profile.min_refuel_gallons,
                "max_refuel_gallons": vehicle.fuel_profile.max_refuel_gallons,
            }
        )
        debug["route"] = self._serialize_debug(
            {
                "id": route.id,
                "total_distance_meters": route.total_distance_meters,
                "total_distance_miles": route.total_distance_meters
                * Decimal("0.000621371192237334"),
                "duration_seconds": route.duration_seconds,
                "geometry_point_count": len(route.geometry_coordinates),
            }
        )
        debug["effective_constraints"] = self._serialize_debug(
            {
                "reserve_gallons": constraints.reserve_gallons,
                "max_allowed_detour_meters": constraints.max_allowed_detour_meters,
            }
        )
        candidate_builder = FuelStationCandidateBuilder(
            self.fuel_station_repository,
            self.detour_calculator,
        )
        build_result = candidate_builder.build(route=route, constraints=constraints)
        candidates = build_result.candidates
        debug["candidate_builder"] = self._serialize_debug(
            {
                "metadata": build_result.metadata,
                "candidates": [
                    {
                        "station_id": candidate.station_id,
                        "route_offset_meters": candidate.route_offset_meters,
                        "distance_from_route_meters": candidate.distance_from_route_meters,
                        "detour_distance_meters": candidate.detour.distance_meters,
                        "detour_time_seconds": candidate.detour.time_seconds,
                        "fuel_type": candidate.fuel_type,
                        "fuel_price_per_gallon": candidate.fuel_price_per_gallon,
                    }
                    for candidate in candidates
                ],
                "audit": build_result.audit,
            }
        )
        context = FuelOptimizationContext(
            route=route,
            vehicle=vehicle,
            initial_fuel_gallons=request.initial_fuel_gallons,
            stations=candidates,
            algorithm=request.algorithm,
            constraints=constraints,
            consumption_model=ConstantMpgFuelConsumptionModel(),
            detour_calculator=self.detour_calculator,
        )

        logger.info(
            "fuel_optimization_started",
            vehicle_id=str(vehicle.id),
            route_id=str(route.id),
            algorithm=request.algorithm.value,
            candidate_count=len(candidates),
            initial_fuel_gallons=str(request.initial_fuel_gallons),
            reserve_gallons=str(constraints.reserve_gallons),
            usable_tank_capacity_gallons=str(
                vehicle.fuel_profile.usable_tank_capacity_gallons
            ),
        )
        logger.info(
            "fuel_optimization_context_resolved",
            vehicle_id=str(vehicle.id),
            route_id=str(route.id),
            context=self._serialize_debug(debug),
        )
        for audit_entry in build_result.audit:
            logger.info(
                "fuel_optimization_candidate_audit",
                vehicle_id=str(vehicle.id),
                route_id=str(route.id),
                station_id=str(audit_entry["station_id"]),
                station_name=audit_entry["name"],
                included=audit_entry["included"],
                reason=audit_entry["reason"],
                fuel_type_normalized=audit_entry["fuel_type_normalized"],
                diesel_price=(
                    str(audit_entry["diesel_price"])
                    if audit_entry["diesel_price"] is not None
                    else None
                ),
                route_offset_meters=str(audit_entry["route_offset_meters"]),
                distance_from_route_meters=str(
                    audit_entry["distance_from_route_meters"]
                ),
                detour_distance_meters=str(audit_entry["detour_distance_meters"]),
                detour_time_seconds=audit_entry["detour_time_seconds"],
            )
        try:
            plan = self.engine.optimize(context)
        except InvalidFuelOptimizationInputError as exc:
            debug["failure"] = {
                "stage": "engine.optimize",
                "error": str(exc),
            }
            logger.warning(
                "fuel_optimization_invalid_input",
                vehicle_id=str(vehicle.id),
                route_id=str(route.id),
                algorithm=request.algorithm.value,
                error=str(exc),
                context=self._serialize_debug(debug),
            )
            raise
        timeline_trace = self._build_algorithm_timeline(plan.debug_trace)
        debug["algorithm_trace"] = self._serialize_debug(timeline_trace)
        debug["algorithm_trace_detailed"] = self._serialize_debug(plan.debug_trace)
        for index, step in enumerate(plan.debug_trace, start=1):
            logger.info(
                "fuel_optimization_algorithm_step",
                vehicle_id=str(vehicle.id),
                route_id=str(route.id),
                algorithm=request.algorithm.value,
                step_number=index,
                trace_event=step.get("event"),
                message=step.get("message"),
                details=self._serialize_debug(step),
            )
        if plan.status is FuelOptimizationStatus.INFEASIBLE:
            logger.info(
                "fuel_optimization_infeasible",
                vehicle_id=str(vehicle.id),
                route_id=str(route.id),
                algorithm=request.algorithm.value,
                candidate_count=len(candidates),
                trace_steps=len(plan.debug_trace),
            )
        else:
            logger.info(
                "fuel_optimization_completed",
                vehicle_id=str(vehicle.id),
                route_id=str(route.id),
                algorithm=request.algorithm.value,
                candidate_count=len(candidates),
                stop_count=plan.number_of_stops,
                total_fuel_purchased=str(plan.total_fuel_purchased_gallons),
                total_fuel_cost=str(plan.total_fuel_cost),
                trace_steps=len(plan.debug_trace),
            )

        run = self.run_repository.create(
            route_id=route.id,
            vehicle_id=vehicle.id,
            initial_fuel_gallons=request.initial_fuel_gallons,
            plan=plan,
        )
        logger.info(
            "fuel_optimization_persisted",
            route_id=str(route.id),
            vehicle_id=str(vehicle.id),
            optimization_run_id=str(run.id),
            status=plan.status.value,
            stop_count=plan.number_of_stops,
        )
        explanation = self._build_explanation(
            vehicle=vehicle,
            route=route,
            constraints=constraints,
            build_result=build_result,
            plan=plan,
        )
        return FuelOptimizationCalculateResponse(
            route_id=route.id,
            vehicle_id=vehicle.id,
            optimization_run_id=run.id,
            status=plan.status,
            algorithm=plan.algorithm,
            algorithm_version=plan.algorithm_version,
            summary=FuelOptimizationSummaryPublic(
                total_fuel_consumed_gallons=plan.total_fuel_consumed_gallons,
                total_fuel_purchased_gallons=plan.total_fuel_purchased_gallons,
                total_fuel_cost=plan.total_fuel_cost,
                total_detour_distance_meters=plan.total_detour_distance_meters,
                total_detour_time_seconds=plan.total_detour_time_seconds,
                number_of_stops=plan.number_of_stops,
                remaining_fuel_gallons=plan.remaining_fuel_gallons,
            ),
            stops=[
                FuelOptimizationStopPublic.model_validate(stop, from_attributes=True)
                for stop in plan.stops
            ],
            explanation=explanation,
            debug=self._serialize_debug(debug) if request.include_debug else None,
        )

    @staticmethod
    def _build_route(route_row) -> Route:
        response = CalculateRouteResponse.model_validate(route_row.provider_response)
        coordinates: list[tuple[float, float]] = []
        for leg in response.routes[0].legs or []:
            if leg.path:
                coordinates.extend(leg.path.coordinates)
        if len(coordinates) < 2:
            raise RouteNotFoundError("Route geometry is not available")
        return Route(
            id=route_row.id,
            total_distance_meters=Decimal(str(route_row.distance_meters)),
            duration_seconds=route_row.duration_seconds,
            geometry_coordinates=coordinates,
        )

    @classmethod
    def _serialize_debug(cls, value: Any) -> Any:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {key: cls._serialize_debug(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._serialize_debug(item) for item in value]
        if isinstance(value, tuple):
            return [cls._serialize_debug(item) for item in value]
        return value

    @classmethod
    def _build_algorithm_timeline(
        cls,
        debug_trace: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        timeline: list[dict[str, Any]] = []

        for step in debug_trace:
            event = step.get("event")
            if event == "initial_state":
                timeline.append(
                    {
                        "step": "start",
                        "remaining_fuel_gallons": step.get("initial_fuel_gallons"),
                        "route_offset_meters": Decimal("0"),
                        "station_id": None,
                        "action": "Start of optimization.",
                    }
                )
            elif event == "travel_to_initial_station":
                reachable_count = step.get("reachable_station_count", 1)
                timeline.append(
                    {
                        "step": "arrival",
                        "remaining_fuel_gallons": step.get(
                            "fuel_after_arrival_gallons"
                        ),
                        "route_offset_meters": step.get(
                            "selected_station_route_offset_meters"
                        ),
                        "station_id": step.get("selected_station_id"),
                        "action": f"Arrived at first reachable station (selected from {reachable_count} candidate(s)).",
                    }
                )
            elif event == "travel_to_next_station":
                timeline.append(
                    {
                        "step": "arrival",
                        "remaining_fuel_gallons": step.get(
                            "fuel_after_arrival_gallons"
                        ),
                        "route_offset_meters": step.get(
                            "selected_station_route_offset_meters"
                        ),
                        "station_id": step.get("selected_station_id"),
                        "action": "Arrived at next selected station.",
                    }
                )
            elif event == "refuel_decision":
                fuel_added = step.get("fuel_added_gallons")
                if fuel_added is not None and Decimal(str(fuel_added)) > Decimal("0"):
                    reason = step.get("decision_reason", "unknown")
                    reason_text = cls._format_decision_reason(reason)
                    timeline.append(
                        {
                            "step": "refuel",
                            "remaining_fuel_gallons": step.get("fuel_after_gallons"),
                            "route_offset_meters": None,
                            "station_id": step.get("current_station_id"),
                            "action": (
                                f"Refueled {cls._fmt(fuel_added)} gal at ${cls._fmt(step.get('current_station_price_per_gallon'))}/gal. "
                                f"Reason: {reason_text}."
                            ),
                        }
                    )
            elif event == "destination_reachable":
                timeline.append(
                    {
                        "step": "destination_reachable",
                        "remaining_fuel_gallons": step.get("current_fuel_gallons"),
                        "route_offset_meters": step.get("current_offset_meters"),
                        "station_id": None,
                        "action": "Destination became reachable.",
                    }
                )
            elif event == "no_reachable_station_from_origin":
                timeline.append(
                    {
                        "step": "blocked",
                        "remaining_fuel_gallons": step.get("current_fuel_gallons"),
                        "route_offset_meters": step.get("current_offset_meters"),
                        "station_id": None,
                        "action": "No reachable station from the starting point while preserving reserve.",
                    }
                )
            elif event == "no_reachable_station_after_refuel":
                timeline.append(
                    {
                        "step": "blocked",
                        "remaining_fuel_gallons": step.get("current_fuel_gallons"),
                        "route_offset_meters": step.get("current_offset_meters"),
                        "station_id": step.get("current_station_id"),
                        "action": "After refueling, neither destination nor any next station was reachable.",
                    }
                )
            elif event == "next_station_became_unreachable":
                deficit = step.get("fuel_deficit_gallons")
                timeline.append(
                    {
                        "step": "blocked",
                        "remaining_fuel_gallons": step.get(
                            "fuel_before_travel_gallons"
                        ),
                        "route_offset_meters": None,
                        "station_id": step.get("current_station_id"),
                        "next_station_id": step.get("planned_next_station_id"),
                        "action": f"The planned next station became unreachable (fuel deficit: {cls._fmt(deficit)} gal).",
                    }
                )
            elif event == "optimization_completed_successfully":
                timeline.append(
                    {
                        "step": "finish",
                        "remaining_fuel_gallons": step.get("remaining_fuel_gallons"),
                        "route_offset_meters": None,
                        "station_id": None,
                        "action": "Optimization finished successfully.",
                    }
                )
            elif event == "optimization_infeasible":
                timeline.append(
                    {
                        "step": "stop",
                        "remaining_fuel_gallons": step.get("remaining_fuel_gallons"),
                        "route_offset_meters": None,
                        "station_id": None,
                        "action": "Optimization ended as infeasible.",
                    }
                )

        return timeline

    @classmethod
    def _build_explanation(
        cls,
        *,
        vehicle: Vehicle,
        route: Route,
        constraints: FuelOptimizationConstraints,
        build_result: CandidateBuildResult,
        plan: FuelOptimizationPlan,
    ) -> FuelOptimizationExplanationPublic:
        kept_candidates = build_result.metadata["candidate_count"]
        total_rows = build_result.metadata["rows_received_from_repository"]
        key_points = [
            (
                f"Route length: {cls._fmt(route.total_distance_meters)} m ({cls._fmt(route.total_distance_meters * Decimal('0.000621371192237334'))} mi)."
            ),
            (
                f"Vehicle usable tank: {cls._fmt(vehicle.fuel_profile.usable_tank_capacity_gallons)} gal, reserve: {cls._fmt(constraints.reserve_gallons)} gal, MPG: {cls._fmt(vehicle.fuel_profile.consumption_mpg)}."
            ),
            (
                f"Station search returned {total_rows} rows; {kept_candidates} candidate station(s) were used in the optimization."
            ),
        ]
        excluded_counts: dict[str, int] = {}
        for audit_entry in build_result.audit:
            reason = audit_entry.get("reason")
            if isinstance(reason, str) and reason != "candidate_included":
                excluded_counts[reason] = excluded_counts.get(reason, 0) + 1
        if excluded_counts:
            key_points.append(
                "Filtered out stations: "
                + ", ".join(
                    f"{reason}={count}"
                    for reason, count in sorted(excluded_counts.items())
                )
                + "."
            )
        warnings: list[str] = []
        warnings.append(
            "Detour distance/time is approximate in MVP and is derived from distance to the route rather than road-network routing."
        )

        if kept_candidates == 0:
            warnings.append(
                "No candidate stations survived filtering, so feasibility depended only on the initial fuel and destination distance."
            )

        if plan.status is FuelOptimizationStatus.SUCCESS:
            summary = (
                f"Optimization succeeded with {plan.number_of_stops} stop(s). "
                f"Estimated purchased fuel: {cls._fmt(plan.total_fuel_purchased_gallons)} gal, "
                f"estimated cost: ${cls._fmt(plan.total_fuel_cost)}, remaining fuel at destination: {cls._fmt(plan.remaining_fuel_gallons)} gal."
            )
            outcome = "The destination is reachable under the current reserve policy after applying the computed stop plan."
            if plan.number_of_stops == 0:
                key_points.append(
                    "The algorithm determined that the destination is reachable without any refueling stop."
                )
            else:
                first_stop = plan.stops[0]
                key_points.append(
                    f"First planned stop: station {first_stop.station_id} at {cls._fmt(first_stop.route_offset_meters)} m, "
                    f"adding {cls._fmt(first_stop.fuel_added_gallons)} gal at ${cls._fmt(first_stop.fuel_price_per_gallon)}/gal."
                )
                if plan.number_of_stops > 1:
                    key_points.append(
                        f"The plan uses {plan.number_of_stops} total stops; see debug/logs for the full per-stop sequence."
                    )
        else:
            summary = f"Optimization is infeasible. Remaining fuel at the failure point: {cls._fmt(plan.remaining_fuel_gallons)} gal."
            outcome = "The algorithm could not find a sequence of reachable stations and/or the destination without violating the reserve constraint."
            infeasible_reasons = cls._extract_infeasible_reasons(plan)
            key_points.extend(infeasible_reasons)

        skipped_station_stats = cls._build_skipped_station_stats(build_result.audit)

        return FuelOptimizationExplanationPublic(
            summary=summary,
            outcome=outcome,
            key_points=key_points,
            warnings=warnings,
            skipped_station_stats=skipped_station_stats,
        )

    @classmethod
    def _extract_infeasible_reasons(cls, plan: FuelOptimizationPlan) -> list[str]:
        lines: list[str] = []
        for step in plan.debug_trace:
            event = step.get("event")
            if event == "initial_state":
                lines.append(
                    f"Start state: {cls._fmt(step.get('initial_fuel_gallons'))} gal available, "
                    f"reserve requirement {cls._fmt(step.get('reserve_gallons'))} gal, "
                    f"{step.get('station_count')} candidate station(s)."
                )
            elif event == "no_reachable_station_from_origin":
                lines.append(
                    "At the starting point, no candidate station could be reached without dropping below reserve."
                )
            elif event == "no_reachable_station_after_refuel":
                lines.append(
                    "After refueling, neither the destination nor any further station was reachable while preserving reserve."
                )
            elif event == "next_station_became_unreachable":
                deficit = step.get("fuel_deficit_gallons")
                lines.append(
                    f"A planned next station ({step.get('planned_next_station_id')}) would require "
                    f"{cls._fmt(deficit)} gal more than available to reach it while preserving reserve."
                )
        if not lines:
            lines.append(
                "See debug/logs for the exact decision sequence that led to the infeasible result."
            )
        return lines

    @classmethod
    def _build_skipped_station_stats(
        cls,
        audit: list[dict[str, Any]],
    ) -> list[FuelOptimizationSkippedStationStatPublic]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for entry in audit:
            reason = entry.get("reason")
            if not isinstance(reason, str) or reason == "candidate_included":
                continue
            grouped.setdefault(reason, []).append(entry)

        stats: list[FuelOptimizationSkippedStationStatPublic] = []
        for reason, entries in sorted(
            grouped.items(), key=lambda item: (-len(item[1]), item[0])
        ):
            sample_entries = entries[:5]
            stats.append(
                FuelOptimizationSkippedStationStatPublic(
                    reason=reason,
                    description=cls._reason_description(reason),
                    count=len(entries),
                    sample_points=[
                        FuelOptimizationSkippedStationPointPublic(
                            station_id=entry["station_id"],
                            name=entry["name"],
                            latitude=entry["latitude"],
                            longitude=entry["longitude"],
                        )
                        for entry in sample_entries
                    ],
                    omitted_points_count=max(0, len(entries) - len(sample_entries)),
                )
            )
        return stats

    @staticmethod
    def _reason_description(reason: str) -> str:
        descriptions = {
            "duplicate_station_id": "Station was skipped because another candidate with the same station ID had already been processed.",
            "unsupported_fuel_type": "Station fuel type does not match the required truck diesel fuel type.",
            "missing_diesel_price": "Station has no diesel price, so it cannot be used in a cost-aware fuel optimization run.",
            "not_truck_accessible": "Station is not marked as accessible for both medium and large trucks.",
            "detour_distance_limit_exceeded": "Station was outside the allowed detour distance constraint.",
        }
        return descriptions.get(
            reason, "Station was filtered out by an optimization candidate rule."
        )

    @staticmethod
    def _fmt(value: Any) -> str:
        if value is None:
            return "n/a"
        if isinstance(value, Decimal):
            normalized = value.normalize()
            return format(normalized, "f")
        return str(value)

    @staticmethod
    def _format_decision_reason(reason: str) -> str:
        """Format the decision reason into a human-readable string."""
        reasons = {
            "buy_minimum_to_reach_cheaper_station_plus_reserve": (
                "Buy minimum fuel to reach cheaper station ahead while maintaining reserve"
            ),
            "buy_enough_for_destination_or_until_next_reachable_segment": (
                "Buy enough fuel to reach destination or next reachable station segment"
            ),
        }
        return reasons.get(reason, reason)
