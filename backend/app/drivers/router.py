"""Driver endpoints.

Mounted at ``/drivers`` rather than under ``/users`` so the static ``drivers``
path can never be shadowed by the ``/users/{user_id}`` dynamic segment.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import require_roles
from app.drivers.dependencies import DriverRepositoryDep
from app.drivers.models import DriverProfile
from app.drivers.schemas import (
    DriverProfilePublic,
    DriverProfileUpdate,
    DriverPublic,
    DriversPublic,
)
from app.models import User, UserRole

router = APIRouter(prefix="/drivers", tags=["drivers"])

DispatcherUser = Annotated[User, Depends(require_roles(UserRole.DISPATCHER))]
DriverUser = Annotated[User, Depends(require_roles(UserRole.DRIVER))]


def _profile_public(profile: DriverProfile | None) -> DriverProfilePublic | None:
    if profile is None:
        return None
    return DriverProfilePublic.model_validate(profile, from_attributes=True)


def _driver_public(user: User, profile: DriverProfile | None) -> DriverPublic:
    return DriverPublic(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        profile=_profile_public(profile),
    )


@router.get("/", response_model=DriversPublic)
def list_drivers(
    repository: DriverRepositoryDep,
    _dispatcher: DispatcherUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> DriversPublic:
    """List drivers for the dispatcher's trip assignment picker."""
    drivers = repository.list_drivers(skip=skip, limit=limit)
    profiles = repository.get_profiles([driver.id for driver in drivers])
    return DriversPublic(
        data=[_driver_public(driver, profiles.get(driver.id)) for driver in drivers],
        count=repository.count_drivers(),
    )


@router.get("/me/profile", response_model=DriverProfilePublic)
def read_own_profile(
    repository: DriverRepositoryDep,
    current_user: DriverUser,
) -> DriverProfilePublic:
    """Return the signed-in driver's own profile, empty if never filled in."""
    profile = repository.get_profile(current_user.id)
    return _profile_public(profile) or DriverProfilePublic()


@router.put("/me/profile", response_model=DriverProfilePublic)
def update_own_profile(
    payload: DriverProfileUpdate,
    repository: DriverRepositoryDep,
    current_user: DriverUser,
) -> DriverProfilePublic:
    profile = repository.upsert_profile(
        current_user.id, payload.model_dump(exclude_unset=True)
    )
    return _profile_public(profile) or DriverProfilePublic()


@router.get("/{user_id}", response_model=DriverPublic)
def read_driver(
    user_id: uuid.UUID,
    repository: DriverRepositoryDep,
    _dispatcher: DispatcherUser,
) -> DriverPublic:
    driver = repository.get_driver(user_id)
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    return _driver_public(driver, repository.get_profile(driver.id))


@router.put("/{user_id}/profile", response_model=DriverPublic)
def update_driver_profile(
    user_id: uuid.UUID,
    payload: DriverProfileUpdate,
    repository: DriverRepositoryDep,
    _dispatcher: DispatcherUser,
) -> DriverPublic:
    driver = repository.get_driver(user_id)
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    profile = repository.upsert_profile(
        driver.id, payload.model_dump(exclude_unset=True)
    )
    return _driver_public(driver, profile)
