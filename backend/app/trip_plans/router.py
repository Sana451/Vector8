"""Trip plan endpoints."""

import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.deps import require_roles
from app.models import User, UserRole
from app.trip_plans.dependencies import TripPlanServiceDep
from app.trip_plans.domain import EXPORT_MEDIA_TYPES, TripPlanExportFormat
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
from app.trip_plans.schemas import (
    TripPlanAssignRequest,
    TripPlanCreateRequest,
    TripPlanDetailPublic,
    TripPlanRefineRequest,
    TripPlanSharedPublic,
    TripPlanSharePublic,
    TripPlanShareRequest,
    TripPlansPublic,
    TripPlanStatusUpdateRequest,
)

router = APIRouter(prefix="/trip-plans", tags=["trip-plans"])

DispatcherUser = Annotated[User, Depends(require_roles(UserRole.DISPATCHER))]
DriverUser = Annotated[User, Depends(require_roles(UserRole.DRIVER))]
AnyRoleUser = Annotated[
    User, Depends(require_roles(UserRole.DISPATCHER, UserRole.DRIVER))
]

NOT_FOUND_ERRORS = (
    TripPlanNotFoundError,
    BaseRouteNotFoundError,
    OptimizationRunNotFoundError,
    DriverNotFoundError,
)
BAD_REQUEST_ERRORS = (
    NoStopsToRefineError,
    UnsupportedProviderError,
    InvalidTripPlanStatusError,
)

UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _filename_stem(name: str) -> str:
    """Make a trip name safe for a Content-Disposition filename."""
    stem = UNSAFE_FILENAME_CHARS.sub("-", name).strip("-")
    return stem or "trip"


@router.post("/", response_model=TripPlanDetailPublic, status_code=201)
async def create_trip_plan(
    request: TripPlanCreateRequest,
    service: TripPlanServiceDep,
    current_user: DispatcherUser,
) -> TripPlanDetailPublic:
    """Save an optimizer result as a trip and refine its route."""
    try:
        trip_plan = await service.create(
            owner_id=current_user.id,
            optimization_run_id=request.optimization_run_id,
            name=request.name,
            provider=request.provider,
            stop_duration_minutes=request.stop_duration_minutes,
        )
    except NOT_FOUND_ERRORS as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BAD_REQUEST_ERRORS as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return service.to_detail(trip_plan)


@router.get("/", response_model=TripPlansPublic)
def list_trip_plans(
    service: TripPlanServiceDep,
    current_user: DispatcherUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> TripPlansPublic:
    """Trips the dispatcher created; admins see every trip."""
    repository = service.repository
    if current_user.role == UserRole.ADMIN or current_user.is_superuser:
        trip_plans = repository.list_all(skip=skip, limit=limit)
        count = repository.count_all()
    else:
        trip_plans = repository.list_for_owner(current_user.id, skip=skip, limit=limit)
        count = repository.count_for_owner(current_user.id)
    return TripPlansPublic(
        data=[service.to_public(trip_plan) for trip_plan in trip_plans],
        count=count,
    )


@router.get("/my", response_model=TripPlansPublic)
def list_my_trip_plans(
    service: TripPlanServiceDep,
    current_user: DriverUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> TripPlansPublic:
    """Trips assigned to the signed-in driver."""
    repository = service.repository
    trip_plans = repository.list_for_driver(current_user.id, skip=skip, limit=limit)
    return TripPlansPublic(
        data=[service.to_public(trip_plan) for trip_plan in trip_plans],
        count=repository.count_for_driver(current_user.id),
    )


@router.get("/shared/{share_token}", response_model=TripPlanSharedPublic)
def read_shared_trip_plan(
    share_token: str,
    service: TripPlanServiceDep,
) -> TripPlanSharedPublic:
    """Read-only trip view for a contractor without an account.

    Unauthenticated on purpose: possession of the token is the credential, so
    a revoked token must become a plain 404 and leak nothing.
    """
    try:
        trip_plan = service.get_shared(share_token)
    except TripPlanNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return service.to_shared(trip_plan)


@router.get("/{trip_plan_id}", response_model=TripPlanDetailPublic)
def read_trip_plan(
    trip_plan_id: uuid.UUID,
    service: TripPlanServiceDep,
    current_user: AnyRoleUser,
) -> TripPlanDetailPublic:
    try:
        trip_plan = service.get_for_user(trip_plan_id, current_user)
    except NOT_FOUND_ERRORS as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TripPlanAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return service.to_detail(trip_plan)


@router.post("/{trip_plan_id}/refine", response_model=TripPlanDetailPublic)
async def refine_trip_plan(
    trip_plan_id: uuid.UUID,
    request: TripPlanRefineRequest,
    service: TripPlanServiceDep,
    current_user: DispatcherUser,
) -> TripPlanDetailPublic:
    """Recalculate the refined route, e.g. after the optimizer changed."""
    try:
        trip_plan = service.get_for_user(trip_plan_id, current_user)
        trip_plan = await service.refine(
            trip_plan,
            provider=request.provider,
            stop_duration_minutes=request.stop_duration_minutes,
            force_refresh=request.force_refresh,
        )
    except NOT_FOUND_ERRORS as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TripPlanAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except BAD_REQUEST_ERRORS as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return service.to_detail(trip_plan)


@router.post("/{trip_plan_id}/assign", response_model=TripPlanDetailPublic)
def assign_trip_plan(
    trip_plan_id: uuid.UUID,
    request: TripPlanAssignRequest,
    service: TripPlanServiceDep,
    current_user: DispatcherUser,
) -> TripPlanDetailPublic:
    """Assign the trip to a driver, or unassign it with a null driver id."""
    try:
        trip_plan = service.get_for_user(trip_plan_id, current_user)
        trip_plan = service.assign(
            trip_plan, driver_id=request.driver_id, assigned_by=current_user
        )
    except NOT_FOUND_ERRORS as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TripPlanAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return service.to_detail(trip_plan)


@router.patch("/{trip_plan_id}/status", response_model=TripPlanDetailPublic)
def update_trip_plan_status(
    trip_plan_id: uuid.UUID,
    request: TripPlanStatusUpdateRequest,
    service: TripPlanServiceDep,
    current_user: AnyRoleUser,
) -> TripPlanDetailPublic:
    """Move the trip along its lifecycle (the driver reports progress)."""
    try:
        trip_plan = service.get_for_user(trip_plan_id, current_user)
        trip_plan = service.update_status(
            trip_plan, status=request.status, user=current_user
        )
    except NOT_FOUND_ERRORS as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TripPlanAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except BAD_REQUEST_ERRORS as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return service.to_detail(trip_plan)


@router.post("/{trip_plan_id}/share", response_model=TripPlanSharePublic)
def share_trip_plan(
    trip_plan_id: uuid.UUID,
    request: TripPlanShareRequest,
    service: TripPlanServiceDep,
    current_user: DispatcherUser,
) -> TripPlanSharePublic:
    """Issue a public link for the trip, or revoke it with `enabled=false`."""
    try:
        trip_plan = service.get_for_user(trip_plan_id, current_user)
        trip_plan = service.set_share(
            trip_plan, enabled=request.enabled, user=current_user
        )
    except NOT_FOUND_ERRORS as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TripPlanAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return TripPlanSharePublic(share_token=trip_plan.share_token)


@router.get(
    "/{trip_plan_id}/export.{export_format}",
    response_class=Response,
    responses={
        200: {
            "content": {
                "application/gpx+xml": {},
                "application/vnd.google-earth.kml+xml": {},
                "text/csv": {},
            },
            "description": "Trip plan rendered for a navigator or a spreadsheet.",
        }
    },
)
def export_trip_plan(
    trip_plan_id: uuid.UUID,
    export_format: TripPlanExportFormat,
    service: TripPlanServiceDep,
    current_user: AnyRoleUser,
) -> Response:
    """Download the trip as GPX, KML or CSV."""
    try:
        trip_plan = service.get_for_user(trip_plan_id, current_user)
    except NOT_FOUND_ERRORS as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TripPlanAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    content = service.export(trip_plan, export_format)
    filename = f"{_filename_stem(trip_plan.name)}.{export_format.value}"
    return Response(
        content=content,
        media_type=EXPORT_MEDIA_TYPES[export_format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{trip_plan_id}", status_code=204)
def delete_trip_plan(
    trip_plan_id: uuid.UUID,
    service: TripPlanServiceDep,
    current_user: DispatcherUser,
) -> None:
    try:
        trip_plan = service.get_for_user(trip_plan_id, current_user)
    except NOT_FOUND_ERRORS as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TripPlanAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    service.repository.delete(trip_plan)
