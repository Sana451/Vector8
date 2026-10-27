from typing import Annotated

from fastapi import Depends

from app.api.deps import SessionDep
from app.fleet.repository import VehicleRepository
from app.fuel_optimization.explain import FuelOptimizationExplainer
from app.fuel_optimization.repository import (
    FuelOptimizationRunRepository,
    RouteCalculationQueryRepository,
)
from app.fuel_optimization.service import OptimizeFuelUseCase
from app.llm import LLMProviderNotConfiguredError, create_llm_provider
from app.map.repository import FuelStationRepository


def get_fuel_optimization_explainer() -> FuelOptimizationExplainer:
    try:
        provider = create_llm_provider()
    except LLMProviderNotConfiguredError:
        provider = None
    return FuelOptimizationExplainer(provider)


FuelOptimizationExplainerDep = Annotated[
    FuelOptimizationExplainer, Depends(get_fuel_optimization_explainer)
]


def get_optimize_fuel_use_case(session: SessionDep) -> OptimizeFuelUseCase:
    return OptimizeFuelUseCase(
        vehicle_repository=VehicleRepository(session),
        route_repository=RouteCalculationQueryRepository(session),
        fuel_station_repository=FuelStationRepository(session),
        run_repository=FuelOptimizationRunRepository(session),
    )


OptimizeFuelUseCaseDep = Annotated[
    OptimizeFuelUseCase, Depends(get_optimize_fuel_use_case)
]
