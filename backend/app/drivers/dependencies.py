"""Driver dependencies."""

from typing import Annotated

from fastapi import Depends

from app.api.deps import SessionDep
from app.drivers.repository import DriverRepository


def get_driver_repository(session: SessionDep) -> DriverRepository:
    return DriverRepository(session)


DriverRepositoryDep = Annotated[DriverRepository, Depends(get_driver_repository)]
