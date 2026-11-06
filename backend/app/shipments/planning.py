"""Plan a trip for a shipment.

Turning a shipment into a trip reuses the existing pipeline unchanged: build a
route, run the fuel optimizer on it, save the result as a trip plan. What this
module adds is only the glue: where the route starts, which stops it passes
through, and which vehicle is the natural one to send.

The vehicle's position is a hint, never a requirement. A dispatcher can always
type an origin, so a missing or stale position degrades the suggestion list
instead of blocking planning.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from pydantic import BaseModel, Field
from sqlmodel import Session

from app.core.datetime import get_datetime_utc
from app.fleet.models import VehicleStatus
from app.fleet.position_repository import PositionReading, VehiclePositionRepository
from app.fleet.positions import VehiclePositionSource
from app.fleet.repository import VehicleRepository
from app.fuel_optimization.domain import FuelOptimizationStatus
from app.fuel_optimization.schemas import (
    FuelOptimizationCalculateRequest,
    FuelOptimizationCalculateResponse,
    FuelOptimizationConstraintsInput,
)
from app.fuel_optimization.service import OptimizeFuelUseCase
from app.providers.geo import GeoJSONMultiPoint, GeoJSONPoint
from app.routing.exceptions import RoutingError, RoutingNoRouteFoundError
from app.routing.schemas import (
    CalculateRouteRequest,
    RoutePlanningLocations,
    VehicleRoutingProfile,
)
from app.routing.service import RoutingService
from app.shipments.domain import PlanningStatus, StopKind
from app.shipments.exceptions import ShipmentNotPlannableError
from app.shipments.service import ShipmentService
from app.trip_plans.models import TripPlan
from app.trip_plans.schemas import TripPlanStopSnapshot
from app.trip_plans.service import TripPlanService

STALE_POSITION_AFTER = timedelta(hours=24)


class PlanningVehicleNotFoundError(ShipmentNotPlannableError):
    pass


class RouteUnavailableError(ShipmentNotPlannableError):
    """The routing provider could not build a route through the stops."""


class RouteNotFoundError(RouteUnavailableError):
    """The provider answered, but no truck route exists between the stops."""


class PlanningInfeasibleError(ShipmentNotPlannableError):
    """The optimizer found no feasible refuel plan; nothing is saved as a trip."""

    def __init__(
        self,
        *,
        optimization_run_id: uuid.UUID,
        route_id: uuid.UUID,
        reasons: list[str],
    ) -> None:
        super().__init__("Fuel plan is infeasible: " + "; ".join(reasons))
        self.optimization_run_id = optimization_run_id
        self.route_id = route_id
        self.reasons = reasons


class VehicleSuggestion(BaseModel):
    vehicle_id: uuid.UUID
    name: str
    unit_number: str
    distance_to_pickup_meters: float | None = Field(
        default=None,
        description="Straight-line distance to the first stop; null without a position.",
    )
    position_source: VehiclePositionSource | None = None
    position_label: str | None = None
    position_recorded_at: str | None = None
    is_position_stale: bool = False


class VehicleSuggestionsPublic(BaseModel):
    data: list[VehicleSuggestion]


class ShipmentPlanRequest(BaseModel):
    vehicle_id: uuid.UUID
    initial_fuel_gallons: Decimal = Field(ge=0)
    origin: tuple[float, float] | None = Field(
        default=None,
        description="[longitude, latitude]. Defaults to the vehicle's last position.",
    )
    origin_label: str | None = Field(default=None, max_length=255)
    destination: tuple[float, float] | None = Field(
        default=None,
        description=(
            "[longitude, latitude]. Defaults to the shipment's last stop; when "
            "given, every shipment stop becomes an intermediate point."
        ),
    )
    destination_label: str | None = Field(default=None, max_length=255)
    constraints: FuelOptimizationConstraintsInput | None = Field(
        default=None,
        description="Same fuel constraints the /map optimizer accepts.",
    )
    stop_duration_minutes: int | None = Field(default=None, ge=0, le=1440)
    name: str | None = Field(default=None, max_length=255)


class ShipmentPlanningService:
    def __init__(
        self,
        *,
        session: Session,
        shipment_service: ShipmentService,
        routing_service: RoutingService,
        optimize_use_case: OptimizeFuelUseCase,
        trip_plan_service: TripPlanService,
    ):
        self.session = session
        self.shipment_service = shipment_service
        self.routing_service = routing_service
        self.optimize_use_case = optimize_use_case
        self.trip_plan_service = trip_plan_service
        self.vehicles = VehicleRepository(session)
        self.positions = VehiclePositionRepository(session)

    def suggest_vehicles(
        self, shipment_id: uuid.UUID, *, owner_id: uuid.UUID
    ) -> list[VehicleSuggestion]:
        """Rank active vehicles by distance from their last position to pickup."""
        self.shipment_service._get_owned(shipment_id, owner_id=owner_id)
        points = self.shipment_service.repository.list_stop_points(shipment_id)
        first = next((point for _, point in points if point is not None), None)

        vehicles, _ = self.vehicles.list(limit=1000)
        active = [v for v in vehicles if str(v.status) == VehicleStatus.ACTIVE.value]
        readings = self.positions.latest(
            vehicle_ids=[v.id for v in active],
            distance_to=(
                (first.coordinates[0], first.coordinates[1]) if first else None
            ),
        )

        now = get_datetime_utc()
        suggestions: list[VehicleSuggestion] = []
        for vehicle in active:
            reading: PositionReading | None = readings.get(vehicle.id)
            suggestions.append(
                VehicleSuggestion(
                    vehicle_id=vehicle.id,
                    name=vehicle.name,
                    unit_number=vehicle.unit_number,
                    distance_to_pickup_meters=(
                        reading.distance_meters if reading else None
                    ),
                    position_source=reading.source if reading else None,
                    position_label=reading.label if reading else None,
                    position_recorded_at=(
                        reading.recorded_at.isoformat() if reading else None
                    ),
                    is_position_stale=(
                        reading is not None
                        and reading.source != VehiclePositionSource.TRIP
                        and now - reading.recorded_at > STALE_POSITION_AFTER
                    ),
                )
            )
        suggestions.sort(
            key=lambda s: (
                s.distance_to_pickup_meters is None,
                s.distance_to_pickup_meters or 0.0,
                s.name,
            )
        )
        return suggestions

    async def plan(
        self,
        shipment_id: uuid.UUID,
        request: ShipmentPlanRequest,
        *,
        owner_id: uuid.UUID,
    ) -> TripPlan:
        shipment = self.shipment_service._get_owned(shipment_id, owner_id=owner_id)
        issues = self.shipment_service.validate_for_planning(
            shipment_id, owner_id=owner_id
        )
        if issues:
            raise ShipmentNotPlannableError(
                "; ".join(issue.message for issue in issues)
            )

        vehicle = self.vehicles.get(request.vehicle_id)
        if vehicle is None:
            raise PlanningVehicleNotFoundError("Vehicle not found")

        origin = request.origin
        origin_label = request.origin_label
        if origin is None:
            reading = self.positions.latest(vehicle_ids=[vehicle.id]).get(vehicle.id)
            if reading is None:
                raise ShipmentNotPlannableError(
                    "The vehicle has no recorded position. Record one or pass an origin."
                )
            origin = (reading.longitude, reading.latitude)
            origin_label = origin_label or reading.label

        rows = [
            (stop, point)
            for stop, point in self.shipment_service.repository.list_stops_with_points(
                shipment_id
            )
            if point is not None
        ]
        kinds = [StopKind(str(stop.kind)) for stop, _ in rows]
        coordinates = [
            (point.coordinates[0], point.coordinates[1]) for _, point in rows
        ]
        labels = {
            index: stop.geocoded_address or stop.address_raw
            for index, (stop, _) in enumerate(rows)
        }
        stops = list(zip(kinds, coordinates, strict=True))

        if request.destination is not None:
            destination = request.destination
            through = coordinates
            default_destination_label = None
        else:
            destination = coordinates[-1]
            through = coordinates[:-1]
            default_destination_label = labels[len(coordinates) - 1]

        locations = RoutePlanningLocations(
            origin=GeoJSONPoint(coordinates=origin),
            destination=GeoJSONPoint(coordinates=destination),
            origin_label=origin_label,
            destination_label=request.destination_label or default_destination_label,
            waypoints=GeoJSONMultiPoint(coordinates=through),
        )
        try:
            route = await self.routing_service.calculate_route(
                CalculateRouteRequest(
                    route_planning_locations=locations,
                    vehicle=VehicleRoutingProfile.from_vehicle(vehicle),
                )
            )
        except RoutingNoRouteFoundError as exc:
            raise RouteNotFoundError(str(exc)) from exc
        except RoutingError as exc:
            raise RouteUnavailableError(str(exc)) from exc
        if not route.routes or route.id is None:
            raise RouteNotFoundError("No truck route found between the stops")

        offsets = self._stop_offsets(route, len(through))
        snapshots = self._shipment_snapshots(
            [kind for kind, _ in stops],
            coordinates,
            labels,
            offsets,
            through_count=len(through),
        )

        optimization = self.optimize_use_case.execute(
            FuelOptimizationCalculateRequest(
                route_id=route.id,
                vehicle_id=vehicle.id,
                initial_fuel_gallons=request.initial_fuel_gallons,
                constraints=request.constraints,
            )
        )
        if optimization.status == FuelOptimizationStatus.INFEASIBLE:
            raise PlanningInfeasibleError(
                optimization_run_id=optimization.optimization_run_id,
                route_id=route.id,
                reasons=self._infeasible_reasons(optimization),
            )
        trip_plan = await self.trip_plan_service.create(
            owner_id=owner_id,
            optimization_run_id=optimization.optimization_run_id,
            name=request.name or self._default_name(shipment.reference_number),
            stop_duration_minutes=request.stop_duration_minutes,
            shipment_id=shipment_id,
            shipment_stops=snapshots,
        )

        shipment.planning_status = PlanningStatus.PLANNED
        self.session.add(shipment)
        self.session.commit()
        return trip_plan

    @staticmethod
    def _infeasible_reasons(
        optimization: FuelOptimizationCalculateResponse,
    ) -> list[str]:
        failure = optimization.failure
        if failure is None:
            return [optimization.explanation.outcome]
        return [failure.message]

    @staticmethod
    def _default_name(reference: str | None) -> str:
        return f"Shipment {reference}" if reference else "Shipment trip"

    @staticmethod
    def _stop_offsets(route, waypoint_count: int) -> list[Decimal]:
        """Distance along the route at which each intermediate stop is reached."""
        best = route.routes[0]
        total = best.summary.length_in_meters
        legs = best.legs or []
        if waypoint_count and len(legs) == waypoint_count + 1:
            offsets: list[Decimal] = []
            cumulative = 0
            for leg in legs[:-1]:
                cumulative += leg.summary.length_in_meters
                offsets.append(Decimal(cumulative))
            return offsets
        return [
            Decimal(total * (index + 1) // (waypoint_count + 1))
            for index in range(waypoint_count)
        ]

    @staticmethod
    def _shipment_snapshots(
        kinds: list[StopKind],
        coordinates: list[tuple[float, float]],
        labels: dict[int, str],
        offsets: list[Decimal],
        *,
        through_count: int,
    ) -> list[TripPlanStopSnapshot]:
        """Snapshot the shipment stops that are routing waypoints.

        The destination (when it is the last stop) is framed by the trip plan
        itself, so only intermediate stops need a snapshot.
        """
        return [
            TripPlanStopSnapshot(
                sequence=index + 1,
                kind="pickup" if kinds[index] == StopKind.PICKUP else "dropoff",
                label=labels[index],
                coordinate=coordinates[index],
                route_offset_meters=offsets[index],
            )
            for index in range(through_count)
        ]
