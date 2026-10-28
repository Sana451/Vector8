from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    SessionDep,
    get_current_active_superuser,
    get_dispatcher_or_superuser,
)
from app.fleet.models import VehicleFuelType, VehicleStatus, VehicleType
from app.fleet.repository import VehicleRepository
from app.fleet.schemas import (
    VehicleCreate,
    VehiclePublic,
    VehiclesPublic,
    VehicleUpdate,
)
from app.models import Message

router = APIRouter(prefix="/vehicles", tags=["vehicles"])
write_access = [Depends(get_current_active_superuser)]
read_access = [Depends(get_dispatcher_or_superuser)]


def _to_vehicle_public(vehicle) -> VehiclePublic:
    return VehiclePublic(
        id=vehicle.id,
        name=vehicle.name,
        unit_number=vehicle.unit_number,
        status=VehicleStatus(str(vehicle.status)),
        vehicle_type=VehicleType(str(vehicle.vehicle_type)),
        make=vehicle.make,
        model=vehicle.model,
        year=vehicle.year,
        height_in=vehicle.height_in,
        width_in=vehicle.width_in,
        length_in=vehicle.length_in,
        gross_weight_lbs=vehicle.gross_weight_lbs,
        weight_per_axle_lbs=vehicle.weight_per_axle_lbs,
        axle_count=vehicle.axle_count,
        tires_count=vehicle.tires_count,
        trailer_count=vehicle.trailer_count,
        trailer_length_in=vehicle.trailer_length_in,
        kpra_length_in=vehicle.kpra_length_in,
        payload_capacity_lbs=vehicle.payload_capacity_lbs,
        max_speed_mph=vehicle.max_speed_mph,
        fuel_type=VehicleFuelType(str(vehicle.fuel_type)),
        tank_capacity_gallons=vehicle.tank_capacity_gallons,
        consumption_mpg=vehicle.consumption_mpg,
        created_at=vehicle.created_at,
        updated_at=vehicle.updated_at,
    )


@router.post("/", response_model=VehiclePublic, dependencies=write_access)
def create_vehicle(*, session: SessionDep, vehicle_in: VehicleCreate) -> Any:
    repository = VehicleRepository(session)
    if repository.get_by_unit_number(vehicle_in.unit_number) is not None:
        raise HTTPException(
            status_code=409, detail="Vehicle unit number already exists"
        )
    try:
        vehicle = repository.create(vehicle_in)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_vehicle_public(vehicle)


@router.get("/", response_model=VehiclesPublic, dependencies=read_access)
def list_vehicles(
    session: SessionDep, skip: int = 0, limit: int = 100
) -> VehiclesPublic:
    repository = VehicleRepository(session)
    vehicles, count = repository.list(skip=skip, limit=limit)
    return VehiclesPublic(
        data=[_to_vehicle_public(vehicle) for vehicle in vehicles],
        count=count,
    )


@router.get("/{vehicle_id}", response_model=VehiclePublic, dependencies=read_access)
def get_vehicle(session: SessionDep, vehicle_id: uuid.UUID) -> VehiclePublic:
    repository = VehicleRepository(session)
    vehicle = repository.get(vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return _to_vehicle_public(vehicle)


@router.patch("/{vehicle_id}", response_model=VehiclePublic, dependencies=write_access)
def update_vehicle(
    *,
    session: SessionDep,
    vehicle_id: uuid.UUID,
    vehicle_in: VehicleUpdate,
) -> VehiclePublic:
    repository = VehicleRepository(session)
    vehicle = repository.get(vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if (
        vehicle_in.unit_number is not None
        and vehicle_in.unit_number != vehicle.unit_number
        and repository.get_by_unit_number(vehicle_in.unit_number) is not None
    ):
        raise HTTPException(
            status_code=409, detail="Vehicle unit number already exists"
        )
    try:
        updated = repository.update(vehicle, vehicle_in)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_vehicle_public(updated)


@router.delete("/{vehicle_id}", response_model=Message, dependencies=write_access)
def delete_vehicle(session: SessionDep, vehicle_id: uuid.UUID) -> Message:
    repository = VehicleRepository(session)
    vehicle = repository.get(vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    repository.delete(vehicle)
    return Message(message="Vehicle deleted successfully")
