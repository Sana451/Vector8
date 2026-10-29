"""Trip plan orchestration.

Building a trip plan means taking the stops the fuel optimizer selected and
asking the routing provider for a route that actually drives into each of
them, instead of the approximate detours the optimizer estimates. The refined
route is persisted as an ordinary ``RouteCalculation``, so caching and
geometry storage are reused as-is.
"""

from __future__ import annotations

import secrets
import uuid

from sqlmodel import Session, col, select

from app.core.datetime import get_datetime_utc
from app.core.logging import get_logger
from app.fleet.repository import VehicleRepository
from app.map.models import FuelStation
from app.models import User, UserRole
from app.providers.exceptions import ProviderNotRegisteredError
from app.providers.geo import GeoJSONLineString, GeoJSONMultiPoint, GeoJSONPoint
from app.providers.registry import registry
from app.routing.exceptions import RoutingError
from app.routing.models import RouteCalculation
from app.routing.repository import RouteCalculationRepository
from app.routing.schemas import (
    CalculateRouteRequest,
    CalculateRouteResponse,
    RoutePlanningLocations,
    VehicleRoutingProfile,
)
from app.routing.service import RoutingService
from app.trip_plans.domain import TripPlanExportFormat, TripPlanStatus
from app.trip_plans.exceptions import (
    BaseRouteNotFoundError,
    DriverNotFoundError,
    InvalidTripPlanStatusError,
    NoStopsToRefineError,
    OptimizationRunNotFoundError,
    TripPlanAccessDeniedError,
    TripPlanNotFoundError,
    UnsupportedProviderError,
)
from app.trip_plans.export import build_csv, build_gpx, build_kml
from app.trip_plans.models import TripPlan
from app.trip_plans.repository import (
    OptimizationRunQueryRepository,
    OptimizationStopRow,
    TripPlanRepository,
)
from app.trip_plans.schemas import (
    TripPlanDeltaPublic,
    TripPlanDetailPublic,
    TripPlanPublic,
    TripPlanSharedPublic,
    TripPlanStationDetails,
    TripPlanStopSnapshot,
)

logger = get_logger(__name__)

SECONDS_PER_MINUTE = 60
SHARE_TOKEN_BYTES = 32

# A driver only reports progress on a trip; everything else is the
# dispatcher's decision.
DRIVER_STATUSES = frozenset({TripPlanStatus.IN_PROGRESS, TripPlanStatus.COMPLETED})
DISPATCHER_STATUSES = frozenset(
    {
        TripPlanStatus.ASSIGNED,
        TripPlanStatus.IN_PROGRESS,
        TripPlanStatus.COMPLETED,
        TripPlanStatus.CANCELLED,
    }
)


class TripPlanService:
    def __init__(self, session: Session, routing_service: RoutingService):
        self.session = session
        self.routing_service = routing_service
        self.repository = TripPlanRepository(session)
        self.optimization_repository = OptimizationRunQueryRepository(session)
        self.route_repository = RouteCalculationRepository(session)
        self.vehicle_repository = VehicleRepository(session)

    async def create(
        self,
        *,
        owner_id: uuid.UUID,
        optimization_run_id: uuid.UUID,
        name: str | None = None,
        provider: str | None = None,
        stop_duration_minutes: int | None = None,
    ) -> TripPlan:
        """Create a trip plan and immediately try to refine its route."""
        run = self.optimization_repository.get_run(optimization_run_id)
        if run is None:
            raise OptimizationRunNotFoundError(
                f"Optimization run {optimization_run_id} not found"
            )

        base_route = self.route_repository.get_by_id(run.route_id)
        if base_route is None:
            raise BaseRouteNotFoundError(f"Route {run.route_id} not found")

        stops = self.optimization_repository.list_stops(optimization_run_id)

        trip_plan = TripPlan(
            name=name or self._default_name(base_route),
            owner_id=owner_id,
            vehicle_id=run.vehicle_id,
            base_route_id=base_route.id,
            optimization_run_id=run.id,
            status=TripPlanStatus.DRAFT,
            stops_snapshot=[
                snapshot.model_dump(mode="json")
                for snapshot in self._build_snapshots(stops)
            ],
            base_distance_meters=base_route.distance_meters,
            base_duration_seconds=base_route.duration_seconds,
            origin_label=self._route_label(base_route, "origin_label"),
            destination_label=self._route_label(base_route, "destination_label"),
        )

        return await self.refine(
            trip_plan,
            provider=provider,
            stop_duration_minutes=stop_duration_minutes,
        )

    async def refine(
        self,
        trip_plan: TripPlan,
        *,
        provider: str | None = None,
        stop_duration_minutes: int | None = None,
        force_refresh: bool = False,
    ) -> TripPlan:
        """Ask the routing provider for a route through every selected stop."""
        stops = self.optimization_repository.list_stops(trip_plan.optimization_run_id)
        if not stops:
            raise NoStopsToRefineError("Optimization run has no stops to route through")

        base_route = self.route_repository.get_by_id(trip_plan.base_route_id)
        if base_route is None:
            raise BaseRouteNotFoundError(f"Route {trip_plan.base_route_id} not found")

        request = self._build_request(
            base_route=base_route,
            stops=stops,
            vehicle_id=trip_plan.vehicle_id,
            stop_duration_minutes=stop_duration_minutes,
        )

        routing_service = self._routing_service(provider)

        try:
            response = await routing_service.calculate_route(
                request, force_refresh=force_refresh
            )
        except RoutingError as exc:
            logger.warning(
                "Trip plan refinement failed",
                trip_plan_id=trip_plan.id,
                error=str(exc),
            )
            return self.repository.set_refine_error(trip_plan, str(exc))

        if not response.routes or response.id is None:
            return self.repository.set_refine_error(
                trip_plan, "Routing provider returned no route"
            )

        summary = response.routes[0].summary
        logger.info(
            "Trip plan refined",
            trip_plan_id=trip_plan.id,
            refined_route_id=response.id,
            stops=len(stops),
        )
        return self.repository.set_refined_route(
            trip_plan,
            refined_route_id=response.id,
            refined_provider=routing_service.provider_name,
            refined_distance_meters=summary.length_in_meters,
            refined_duration_seconds=summary.travel_duration_in_seconds,
        )

    def _routing_service(self, provider: str | None) -> RoutingService:
        """Return the routing service to use for a refinement.

        A trip may be refined with a provider other than the configured
        default, so the caller can compare results between vendors.
        """
        if provider is None or provider == self.routing_service.provider_name:
            return self.routing_service

        try:
            adapter = registry.get("routing", provider)
        except ProviderNotRegisteredError as exc:
            raise UnsupportedProviderError(str(exc)) from exc
        return RoutingService(provider=adapter, session=self.session)

    def get(self, trip_plan_id: uuid.UUID) -> TripPlan:
        trip_plan = self.repository.get(trip_plan_id)
        if trip_plan is None:
            raise TripPlanNotFoundError(f"Trip plan {trip_plan_id} not found")
        return trip_plan

    def get_for_user(self, trip_plan_id: uuid.UUID, user: User) -> TripPlan:
        """Return a trip plan only if ``user`` is allowed to see it.

        The check lives here rather than in the router so every entry point
        (including future ones) is covered by the same rule.
        """
        trip_plan = self.get(trip_plan_id)
        if not self.can_access(trip_plan, user):
            raise TripPlanAccessDeniedError(
                "The user doesn't have access to this trip plan"
            )
        return trip_plan

    @staticmethod
    def can_access(trip_plan: TripPlan, user: User) -> bool:
        if user.role == UserRole.ADMIN or user.is_superuser:
            return True
        if user.role == UserRole.DRIVER:
            return trip_plan.assigned_driver_id == user.id
        return trip_plan.owner_id == user.id

    @staticmethod
    def can_manage(trip_plan: TripPlan, user: User) -> bool:
        """Whether the user may assign the trip or delete it."""
        if user.role == UserRole.ADMIN or user.is_superuser:
            return True
        return user.role == UserRole.DISPATCHER and trip_plan.owner_id == user.id

    def assign(
        self, trip_plan: TripPlan, *, driver_id: uuid.UUID | None, assigned_by: User
    ) -> TripPlan:
        """Assign the trip to a driver, or unassign it when ``driver_id`` is None."""
        if not self.can_manage(trip_plan, assigned_by):
            raise TripPlanAccessDeniedError(
                "The user doesn't have access to this trip plan"
            )

        if driver_id is None:
            return self.repository.update(
                trip_plan,
                assigned_driver_id=None,
                assigned_by_id=None,
                assigned_at=None,
                status=self._unassigned_status(trip_plan),
            )

        driver = self.session.get(User, driver_id)
        if driver is None or driver.role != UserRole.DRIVER:
            raise DriverNotFoundError(f"Driver {driver_id} not found")

        return self.repository.update(
            trip_plan,
            assigned_driver_id=driver.id,
            assigned_by_id=assigned_by.id,
            assigned_at=get_datetime_utc(),
            status=TripPlanStatus.ASSIGNED,
        )

    @staticmethod
    def _unassigned_status(trip_plan: TripPlan) -> TripPlanStatus:
        """Roll the lifecycle back to where it was before assignment."""
        if trip_plan.refined_route_id is not None:
            return TripPlanStatus.REFINED
        if trip_plan.refine_error:
            return TripPlanStatus.REFINE_FAILED
        return TripPlanStatus.DRAFT

    def update_status(
        self, trip_plan: TripPlan, *, status: TripPlanStatus, user: User
    ) -> TripPlan:
        allowed = (
            DRIVER_STATUSES
            if user.role == UserRole.DRIVER and not user.is_superuser
            else DISPATCHER_STATUSES
        )
        if status not in allowed:
            raise InvalidTripPlanStatusError(
                f"Status {status} cannot be set by role {user.role}"
            )
        return self.repository.update(trip_plan, status=status)

    def export(self, trip_plan: TripPlan, export_format: TripPlanExportFormat) -> str:
        """Render the trip for a navigator or a spreadsheet.

        The refined geometry is preferred; a trip whose refinement failed still
        exports against the base route so the driver is never left empty-handed.
        """
        route_id = trip_plan.refined_route_id or trip_plan.base_route_id
        geometry = self._geometry(self.route_repository.get_by_id(route_id))
        coordinates = (
            [(point[0], point[1]) for point in geometry.coordinates]
            if geometry is not None
            else []
        )
        stops = self._with_endpoints(trip_plan, geometry)

        if export_format is TripPlanExportFormat.CSV:
            return build_csv(stops)

        builder = build_gpx if export_format is TripPlanExportFormat.GPX else build_kml
        return builder(name=trip_plan.name, stops=stops, coordinates=coordinates)

    @staticmethod
    def _with_endpoints(
        trip_plan: TripPlan, geometry: GeoJSONLineString | None
    ) -> list[TripPlanStopSnapshot]:
        """Frame the fuel stops with the route's start and destination.

        The start and end are derived from the route geometry at read time, so
        trips saved before this existed gain them too without a data migration.
        """
        stops = [
            stop
            for stop in (
                TripPlanStopSnapshot.model_validate(raw)
                for raw in trip_plan.stops_snapshot
            )
            if stop.kind not in ("start", "destination")
        ]
        if geometry is None or not geometry.coordinates:
            return stops

        first, last = geometry.coordinates[0], geometry.coordinates[-1]
        last_sequence = max((stop.sequence for stop in stops), default=0)
        start = TripPlanStopSnapshot(
            sequence=0,
            kind="start",
            label=trip_plan.origin_label or "Start",
            coordinate=(first[0], first[1]),
        )
        destination = TripPlanStopSnapshot(
            sequence=last_sequence + 1,
            kind="destination",
            label=trip_plan.destination_label or "Destination",
            coordinate=(last[0], last[1]),
        )
        return [start, *stops, destination]

    def _attach_stations(
        self, stops: list[TripPlanStopSnapshot]
    ) -> list[TripPlanStopSnapshot]:
        """Enrich refuel stops with the current station record, if it still exists.

        Looked up by ``station_id`` at read time, so trips saved before this
        existed show the same details as the /map popup without a migration.
        Stops whose station has been removed keep ``station=None``.
        """
        station_ids = {stop.station_id for stop in stops if stop.station_id}
        if not station_ids:
            return stops

        rows = self.session.exec(
            select(FuelStation).where(col(FuelStation.id).in_(station_ids))
        ).all()
        by_id = {row.id: row for row in rows}

        enriched: list[TripPlanStopSnapshot] = []
        for stop in stops:
            row = by_id.get(stop.station_id) if stop.station_id else None
            if row is None:
                enriched.append(stop)
                continue
            payload = row.payload or {}
            details = TripPlanStationDetails(
                name=row.name,
                brand=row.brand,
                address=row.address,
                fuel_type=payload.get("fuel_type"),
                diesel_price=row.diesel_price,
                currency=payload.get("currency"),
                has_adblue=bool(payload.get("has_adblue", False)),
                is_open=payload.get("is_open"),
                medium_truck_accessible=row.medium_truck_accessible,
                large_truck_accessible=row.large_truck_accessible,
                phone=payload.get("phone"),
                website=payload.get("website"),
            )
            enriched.append(stop.model_copy(update={"station": details}))
        return enriched

    def set_share(self, trip_plan: TripPlan, *, enabled: bool, user: User) -> TripPlan:
        """Issue or revoke the public link for the trip.

        Re-issuing keeps the existing token so a link already handed to a
        contractor does not silently stop working; revoking clears it, which
        permanently invalidates every copy of the old link.
        """
        if not self.can_manage(trip_plan, user):
            raise TripPlanAccessDeniedError(
                "The user doesn't have access to this trip plan"
            )

        if not enabled:
            return self.repository.update(trip_plan, share_token=None)
        if trip_plan.share_token:
            return trip_plan
        return self.repository.update(
            trip_plan, share_token=secrets.token_urlsafe(SHARE_TOKEN_BYTES)
        )

    def get_shared(self, share_token: str) -> TripPlan:
        """Resolve a public link, or raise as if the trip did not exist."""
        trip_plan = self.repository.get_by_share_token(share_token)
        if trip_plan is None:
            raise TripPlanNotFoundError("Trip plan not found")
        return trip_plan

    def to_shared(self, trip_plan: TripPlan) -> TripPlanSharedPublic:
        route_id = trip_plan.refined_route_id or trip_plan.base_route_id
        geometry = self._geometry(self.route_repository.get_by_id(route_id))
        return TripPlanSharedPublic(
            name=trip_plan.name,
            status=TripPlanStatus(trip_plan.status),
            distance_meters=(
                trip_plan.refined_distance_meters or trip_plan.base_distance_meters
            ),
            duration_seconds=(
                trip_plan.refined_duration_seconds or trip_plan.base_duration_seconds
            ),
            number_of_stops=len(trip_plan.stops_snapshot),
            created_at=trip_plan.created_at,
            stops=self._attach_stations(self._with_endpoints(trip_plan, geometry)),
            geometry=geometry,
        )

    def to_public(self, trip_plan: TripPlan) -> TripPlanPublic:
        # SQLModel table classes skip validation, so a row loaded from the
        # plain string column keeps a ``str`` in a field annotated as an enum.
        # Excluding it from the dump avoids a serialization warning.
        data = trip_plan.model_dump(exclude={"stops_snapshot", "share_token", "status"})
        vehicle = self.vehicle_repository.get(trip_plan.vehicle_id)
        return TripPlanPublic(
            **data,
            status=TripPlanStatus(trip_plan.status),
            number_of_stops=len(trip_plan.stops_snapshot),
            is_shared=trip_plan.share_token is not None,
            vehicle_name=vehicle.name if vehicle is not None else None,
            vehicle_unit_number=vehicle.unit_number if vehicle is not None else None,
        )

    def to_detail(self, trip_plan: TripPlan) -> TripPlanDetailPublic:
        base_route = self.route_repository.get_by_id(trip_plan.base_route_id)
        refined_route = (
            self.route_repository.get_by_id(trip_plan.refined_route_id)
            if trip_plan.refined_route_id is not None
            else None
        )

        delta = None
        if (
            trip_plan.refined_distance_meters is not None
            and trip_plan.refined_duration_seconds is not None
        ):
            delta = TripPlanDeltaPublic(
                distance_meters=(
                    trip_plan.refined_distance_meters - trip_plan.base_distance_meters
                ),
                duration_seconds=(
                    trip_plan.refined_duration_seconds - trip_plan.base_duration_seconds
                ),
            )

        base_geometry = self._geometry(base_route)
        refined_geometry = self._geometry(refined_route)
        vehicle = self.vehicle_repository.get(trip_plan.vehicle_id)
        return TripPlanDetailPublic(
            **self.to_public(trip_plan).model_dump(),
            stops=self._attach_stations(
                self._with_endpoints(trip_plan, refined_geometry or base_geometry)
            ),
            base_geometry=base_geometry,
            refined_geometry=refined_geometry,
            delta=delta,
            usable_tank_gallons=(
                vehicle.usable_tank_capacity_gallons if vehicle is not None else None
            ),
        )

    @staticmethod
    def _route_label(route: RouteCalculation, field: str) -> str | None:
        """Read an address label stored in the base route's request payload."""
        locations = (route.request_data or {}).get("route_planning_locations") or {}
        value = locations.get(field)
        return value if isinstance(value, str) else None

    def _build_request(
        self,
        *,
        base_route: RouteCalculation,
        stops: list[OptimizationStopRow],
        vehicle_id: uuid.UUID,
        stop_duration_minutes: int | None,
    ) -> CalculateRouteRequest:
        base_request = CalculateRouteRequest.model_validate(base_route.request_data)
        locations = base_request.route_planning_locations

        vehicle = self.vehicle_repository.get(vehicle_id)
        vehicle_profile = (
            VehicleRoutingProfile.from_vehicle(vehicle)
            if vehicle is not None
            else base_request.vehicle
        )

        return CalculateRouteRequest(
            route_planning_locations=RoutePlanningLocations(
                origin=GeoJSONPoint(coordinates=locations.origin.coordinates),
                destination=GeoJSONPoint(coordinates=locations.destination.coordinates),
                origin_label=locations.origin_label,
                destination_label=locations.destination_label,
                waypoints=GeoJSONMultiPoint(
                    coordinates=[
                        (float(stop.longitude), float(stop.latitude)) for stop in stops
                    ]
                ),
                waypoint_stop_duration_seconds=(
                    stop_duration_minutes * SECONDS_PER_MINUTE
                    if stop_duration_minutes is not None
                    else None
                ),
            ),
            route_type=base_request.route_type,
            traffic=base_request.traffic,
            vehicle=vehicle_profile,
        )

    @staticmethod
    def _build_snapshots(
        stops: list[OptimizationStopRow],
    ) -> list[TripPlanStopSnapshot]:
        return [
            TripPlanStopSnapshot(
                sequence=stop.sequence,
                kind="refuel",
                label=stop.name,
                station_id=stop.station_id,
                coordinate=(float(stop.longitude), float(stop.latitude)),
                route_offset_meters=stop.route_offset_meters,
                fuel_before_gallons=stop.fuel_before_gallons,
                fuel_added_gallons=stop.fuel_added_gallons,
                fuel_after_gallons=stop.fuel_after_gallons,
                fuel_price_per_gallon=stop.fuel_price_per_gallon,
                fuel_cost=stop.fuel_cost,
                detour_distance_meters=stop.detour_distance_meters,
                detour_time_seconds=stop.detour_time_seconds,
            )
            for stop in stops
        ]

    @staticmethod
    def _geometry(route: RouteCalculation | None) -> GeoJSONLineString | None:
        """Rebuild route geometry by concatenating the legs of the response."""
        if route is None:
            return None

        response = CalculateRouteResponse.model_validate(route.provider_response)
        if not response.routes:
            return None

        coordinates: list[tuple[float, float]] = []
        for leg in response.routes[0].legs or []:
            if leg.path is None:
                continue
            leg_coordinates = list(leg.path.coordinates)
            if (
                coordinates
                and leg_coordinates
                and coordinates[-1] == leg_coordinates[0]
            ):
                leg_coordinates = leg_coordinates[1:]
            coordinates.extend(leg_coordinates)

        if len(coordinates) < 2:
            return None
        return GeoJSONLineString(coordinates=coordinates)

    @staticmethod
    def _default_name(base_route: RouteCalculation) -> str:
        return f"Trip {base_route.created_at:%Y-%m-%d %H:%M}"
