from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_active_superuser
from app.fuel_optimization.dependencies import OptimizeFuelUseCaseDep
from app.fuel_optimization.domain import (
    InvalidFuelOptimizationInputError,
    UnsupportedOptimizationAlgorithmError,
)
from app.fuel_optimization.exceptions import (
    FuelProfileNotFoundError,
    RouteNotFoundError,
    VehicleNotFoundError,
)
from app.fuel_optimization.schemas import (
    FuelOptimizationCalculateRequest,
    FuelOptimizationCalculateResponse,
)

router = APIRouter(
    prefix="/fuel-optimization",
    tags=["fuel-optimization"],
    dependencies=[Depends(get_current_active_superuser)],
)


@router.post("/calculate", response_model=FuelOptimizationCalculateResponse)
def calculate_fuel_optimization(
    request: FuelOptimizationCalculateRequest,
    use_case: OptimizeFuelUseCaseDep,
) -> FuelOptimizationCalculateResponse:
    try:
        return use_case.execute(request)
    except VehicleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RouteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FuelProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UnsupportedOptimizationAlgorithmError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except InvalidFuelOptimizationInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
