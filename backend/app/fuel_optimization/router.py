from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_active_superuser
from app.fuel_optimization.dependencies import (
    FuelOptimizationExplainerDep,
    OptimizeFuelUseCaseDep,
)
from app.fuel_optimization.domain import (
    InvalidFuelOptimizationInputError,
    UnsupportedOptimizationAlgorithmError,
)
from app.fuel_optimization.exceptions import (
    RouteNotFoundError,
    VehicleNotFoundError,
)
from app.fuel_optimization.schemas import (
    FuelOptimizationCalculateRequest,
    FuelOptimizationCalculateResponse,
    FuelOptimizationExplainRequest,
    FuelOptimizationExplainResponse,
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
    except UnsupportedOptimizationAlgorithmError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except InvalidFuelOptimizationInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/explain", response_model=FuelOptimizationExplainResponse)
async def explain_fuel_optimization(
    request: FuelOptimizationExplainRequest,
    explainer: FuelOptimizationExplainerDep,
) -> FuelOptimizationExplainResponse:
    """Explain an optimizer result in plain language and answer follow-ups."""
    answer, source = await explainer.explain(
        request.optimization,
        stop_sequence=request.stop_sequence,
        question=request.question,
        history=[message.model_dump() for message in request.history],
        language=request.language,
    )
    return FuelOptimizationExplainResponse(answer=answer, source=source)
