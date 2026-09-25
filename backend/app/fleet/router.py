from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import SessionDep, get_current_active_superuser
from app.fleet.models import VehicleFuelType, VehicleStatus, VehicleType
from app.fleet.repository import VehicleRepository
from app.fleet.schemas import (
    VehicleCreate,
    VehicleFuelProfilePublic,
    VehiclePublic,
    VehiclesPublic,
    VehicleUpdate,
)
from app.models import Message

router = APIRouter(
    prefix="/vehicles",
    tags=["vehicles"],
    dependencies=[Depends(get_current_active_superuser)],
)


def _to_vehicle_public(repository: VehicleRepository, vehicle) -> VehiclePublic:
    profile = repository.get_fuel_profile(vehicle.fuel_profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Vehicle fuel profile not found")
    return VehiclePublic(
        id=vehicle.id,
        name=vehicle.name,
        unit_number=vehicle.unit_number,
        status=VehicleStatus(str(vehicle.status)),
        vehicle_type=VehicleType(str(vehicle.vehicle_type)),
        make=vehicle.make,
        model=vehicle.model,
        year=vehicle.year,
        routing_profile_id=vehicle.routing_profile_id,
        created_at=vehicle.created_at,
        updated_at=vehicle.updated_at,
        fuel_profile=VehicleFuelProfilePublic(
            id=profile.id,
            name=profile.name,
            fuel_type=VehicleFuelType(str(profile.fuel_type)),
            tank_capacity_gallons=profile.tank_capacity_gallons,
            usable_tank_capacity_gallons=profile.usable_tank_capacity_gallons,
            consumption_mpg=profile.consumption_mpg,
            reserve_gallons=profile.reserve_gallons,
            min_refuel_gallons=profile.min_refuel_gallons,
            max_refuel_gallons=profile.max_refuel_gallons,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        ),
    )


@router.post("/", response_model=VehiclePublic)
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
    return _to_vehicle_public(repository, vehicle)


@router.get("/", response_model=VehiclesPublic)
def list_vehicles(
    session: SessionDep, skip: int = 0, limit: int = 100
) -> VehiclesPublic:
    repository = VehicleRepository(session)
    vehicles, count = repository.list(skip=skip, limit=limit)
    return VehiclesPublic(
        data=[_to_vehicle_public(repository, vehicle) for vehicle in vehicles],
        count=count,
    )


@router.get("/{vehicle_id}", response_model=VehiclePublic)
def get_vehicle(session: SessionDep, vehicle_id: uuid.UUID) -> VehiclePublic:
    repository = VehicleRepository(session)
    vehicle = repository.get(vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return _to_vehicle_public(repository, vehicle)


@router.patch("/{vehicle_id}", response_model=VehiclePublic)
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
    return _to_vehicle_public(repository, updated)


@router.delete("/{vehicle_id}", response_model=Message)
def delete_vehicle(session: SessionDep, vehicle_id: uuid.UUID) -> Message:
    repository = VehicleRepository(session)
    vehicle = repository.get(vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    repository.delete(vehicle)
    return Message(message="Vehicle deleted successfully")
