"""Dependency wiring for the shipments domain."""

from typing import Annotated

from fastapi import Depends

from app.api.deps import SessionDep
from app.fuel_optimization.dependencies import get_optimize_fuel_use_case
from app.fuel_optimization.service import OptimizeFuelUseCase
from app.geocoding.dependencies import get_geocoding_service
from app.geocoding.service import GeocodingService
from app.llm.factory import create_llm_provider
from app.routing.dependencies import get_routing_service
from app.routing.service import RoutingService
from app.shipments.extraction.parser import ShipmentDocumentParser
from app.shipments.planning import ShipmentPlanningService
from app.shipments.service import ShipmentService
from app.trip_plans.dependencies import get_trip_plan_service
from app.trip_plans.service import TripPlanService


def get_document_parser() -> ShipmentDocumentParser:
    """Build the document parser on the configured LLM provider."""
    return ShipmentDocumentParser(create_llm_provider())


def get_shipment_service(
    session: SessionDep,
    parser: ShipmentDocumentParser = Depends(get_document_parser),
    geocoding_service: GeocodingService = Depends(get_geocoding_service),
) -> ShipmentService:
    """Build the shipment service."""
    return ShipmentService(
        session=session,
        parser=parser,
        geocoding_service=geocoding_service,
    )


ShipmentServiceDep = Annotated[ShipmentService, Depends(get_shipment_service)]


def get_shipment_planning_service(
    session: SessionDep,
    shipment_service: ShipmentServiceDep,
    routing_service: RoutingService = Depends(get_routing_service),
    optimize_use_case: OptimizeFuelUseCase = Depends(get_optimize_fuel_use_case),
    trip_plan_service: TripPlanService = Depends(get_trip_plan_service),
) -> ShipmentPlanningService:
    return ShipmentPlanningService(
        session=session,
        shipment_service=shipment_service,
        routing_service=routing_service,
        optimize_use_case=optimize_use_case,
        trip_plan_service=trip_plan_service,
    )


ShipmentPlanningServiceDep = Annotated[
    ShipmentPlanningService, Depends(get_shipment_planning_service)
]
