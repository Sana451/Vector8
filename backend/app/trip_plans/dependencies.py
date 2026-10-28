"""Trip plan dependencies."""

from typing import Annotated

from fastapi import Depends

from app.api.deps import SessionDep
from app.routing.dependencies import get_routing_service
from app.routing.service import RoutingService
from app.trip_plans.service import TripPlanService


def get_trip_plan_service(
    session: SessionDep,
    routing_service: RoutingService = Depends(get_routing_service),
) -> TripPlanService:
    return TripPlanService(session=session, routing_service=routing_service)


TripPlanServiceDep = Annotated[TripPlanService, Depends(get_trip_plan_service)]
