"""Shipment intake endpoints."""

import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile

from app.api.deps import require_roles
from app.fuel_optimization.exceptions import FuelOptimizationError
from app.models import User, UserRole
from app.shipments.dependencies import ShipmentPlanningServiceDep, ShipmentServiceDep
from app.shipments.domain import PlanningStatus
from app.shipments.exceptions import (
    DocumentParsingError,
    DocumentTextExtractionError,
    DocumentTooLargeError,
    ShipmentAccessDeniedError,
    ShipmentDocumentNotFoundError,
    ShipmentNotFoundError,
    ShipmentNotPlannableError,
    UnsupportedDocumentTypeError,
)
from app.shipments.planning import (
    PlanningVehicleNotFoundError,
    RouteNotFoundError,
    RouteUnavailableError,
    ShipmentPlanRequest,
    VehicleSuggestionsPublic,
)
from app.shipments.schemas import (
    ShipmentDetailPublic,
    ShipmentsPublic,
    ShipmentUpdateRequest,
    ShipmentUploadResponse,
    ShipmentValidationIssue,
)
from app.trip_plans.schemas import TripPlanDetailPublic

router = APIRouter(prefix="/shipments", tags=["shipments"])

DispatcherUser = Annotated[User, Depends(require_roles(UserRole.DISPATCHER))]

UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(name: str) -> str:
    """Make an uploaded name safe for a Content-Disposition header."""
    cleaned = UNSAFE_FILENAME_CHARS.sub("-", name).strip("-")
    return cleaned or "document.pdf"


@router.post("/upload", response_model=ShipmentUploadResponse, status_code=201)
async def upload_shipment_document(
    service: ShipmentServiceDep,
    current_user: DispatcherUser,
    file: Annotated[UploadFile, File(description="Rate confirmation PDF")],
) -> ShipmentUploadResponse:
    """Upload a rate confirmation and extract a shipment from it."""
    content = await file.read()
    try:
        shipment, is_duplicate = await service.upload_document(
            content=content,
            filename=file.filename or "document.pdf",
            content_type=file.content_type,
            owner_id=current_user.id,
        )
    except (UnsupportedDocumentTypeError, DocumentTooLargeError) as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except DocumentTextExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DocumentParsingError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ShipmentUploadResponse(
        shipment=service.build_detail(shipment),
        issues=service.validate_for_planning(shipment.id, owner_id=current_user.id),
        is_duplicate=is_duplicate,
    )


@router.get("/", response_model=ShipmentsPublic)
def list_shipments(
    service: ShipmentServiceDep,
    current_user: DispatcherUser,
    planning_status: Annotated[PlanningStatus | None, Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ShipmentsPublic:
    """List the current user's shipments, newest first."""
    data, count = service.list_shipments(
        owner_id=current_user.id,
        planning_status=planning_status,
        skip=skip,
        limit=limit,
    )
    return ShipmentsPublic(data=data, count=count)


@router.get("/{shipment_id}", response_model=ShipmentDetailPublic)
def get_shipment(
    shipment_id: uuid.UUID,
    service: ShipmentServiceDep,
    current_user: DispatcherUser,
) -> ShipmentDetailPublic:
    """Return a shipment with its stops and document metadata."""
    try:
        return service.get_detail(shipment_id, owner_id=current_user.id)
    except ShipmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ShipmentAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.patch("/{shipment_id}", response_model=ShipmentDetailPublic)
async def update_shipment(
    shipment_id: uuid.UUID,
    request: ShipmentUpdateRequest,
    service: ShipmentServiceDep,
    current_user: DispatcherUser,
) -> ShipmentDetailPublic:
    """Apply corrections to an extracted shipment."""
    try:
        shipment = await service.update(shipment_id, request, owner_id=current_user.id)
    except ShipmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ShipmentAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return service.build_detail(shipment)


@router.post("/{shipment_id}/reparse", response_model=ShipmentDetailPublic)
async def reparse_shipment(
    shipment_id: uuid.UUID,
    service: ShipmentServiceDep,
    current_user: DispatcherUser,
) -> ShipmentDetailPublic:
    """Re-run extraction on the shipment's document, discarding manual edits."""
    try:
        shipment = await service.reparse(shipment_id, owner_id=current_user.id)
    except (ShipmentNotFoundError, ShipmentDocumentNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ShipmentAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except DocumentTextExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DocumentParsingError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return service.build_detail(shipment)


@router.get("/{shipment_id}/validation", response_model=list[ShipmentValidationIssue])
def validate_shipment(
    shipment_id: uuid.UUID,
    service: ShipmentServiceDep,
    current_user: DispatcherUser,
) -> list[ShipmentValidationIssue]:
    """Report what prevents this shipment from being planned."""
    try:
        return service.validate_for_planning(shipment_id, owner_id=current_user.id)
    except ShipmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ShipmentAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/documents/{document_id}/file")
def download_shipment_document(
    document_id: uuid.UUID,
    service: ShipmentServiceDep,
    current_user: DispatcherUser,
) -> Response:
    """Serve the original uploaded file for side-by-side review."""
    try:
        document = service.get_document(document_id, owner_id=current_user.id)
    except (ShipmentDocumentNotFoundError, ShipmentNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ShipmentAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    filename = _safe_filename(document.filename)
    return Response(
        content=document.content,
        media_type=document.content_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get(
    "/{shipment_id}/vehicle-suggestions", response_model=VehicleSuggestionsPublic
)
def suggest_vehicles(
    shipment_id: uuid.UUID,
    planning: ShipmentPlanningServiceDep,
    current_user: DispatcherUser,
) -> VehicleSuggestionsPublic:
    """Active vehicles ordered by distance from their last position to pickup."""
    try:
        data = planning.suggest_vehicles(shipment_id, owner_id=current_user.id)
    except ShipmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ShipmentAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return VehicleSuggestionsPublic(data=data)


@router.post(
    "/{shipment_id}/plan", response_model=TripPlanDetailPublic, status_code=201
)
async def plan_shipment(
    shipment_id: uuid.UUID,
    request: ShipmentPlanRequest,
    planning: ShipmentPlanningServiceDep,
    current_user: DispatcherUser,
) -> TripPlanDetailPublic:
    """Route a vehicle to and through the shipment stops and save the trip."""
    try:
        trip_plan = await planning.plan(shipment_id, request, owner_id=current_user.id)
    except ShipmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ShipmentAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except PlanningVehicleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RouteNotFoundError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RouteUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ShipmentNotPlannableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FuelOptimizationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return planning.trip_plan_service.to_detail(trip_plan)


@router.delete("/{shipment_id}", status_code=204)
def delete_shipment(
    shipment_id: uuid.UUID,
    service: ShipmentServiceDep,
    current_user: DispatcherUser,
) -> Response:
    """Delete a shipment together with its stops and documents."""
    try:
        service.delete(shipment_id, owner_id=current_user.id)
    except ShipmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ShipmentAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return Response(status_code=204)
