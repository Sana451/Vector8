"""
Map module dependencies.

Wires layer services to their configured providers through the registry.
"""

from typing import Annotated

from fastapi import Depends

from app.api.deps import SessionDep
from app.core.config import settings
from app.geocoding.dependencies import get_geocoding_service
from app.geocoding.service import GeocodingService
from app.map.service import MapLayerService
from app.map.services import (
    FuelService,
    HerePoiService,
    TrafficService,
    TruckRestrictionService,
)
from app.providers.base import (
    FuelStationProvider,
    RestAreaProvider,
    TrafficProvider,
    TruckRestrictionProvider,
)
from app.providers.registry import registry
from app.routing.dependencies import get_routing_service
from app.routing.service import RoutingService


def get_traffic_provider() -> TrafficProvider:
    """Resolve the configured traffic provider."""
    return registry.get("traffic", settings.TRAFFIC_PROVIDER)


def get_fuel_provider() -> FuelStationProvider:
    """Resolve the configured fuel station provider."""
    return registry.get("fuel", settings.FUEL_PROVIDER)


def get_truck_restriction_provider() -> TruckRestrictionProvider:
    """Resolve the configured truck restriction provider."""
    return registry.get("truck_restrictions", settings.TRUCK_RESTRICTION_PROVIDER)


def get_rest_area_provider() -> RestAreaProvider:
    """Resolve the configured rest area provider."""
    return registry.get("rest_areas", settings.REST_AREAS_PROVIDER)


def get_traffic_service(
    session: SessionDep,
    provider: TrafficProvider = Depends(get_traffic_provider),
) -> TrafficService:
    """Build the traffic layer service."""
    return TrafficService(provider=provider, session=session)


def get_fuel_service(
    session: SessionDep,
    provider: FuelStationProvider = Depends(get_fuel_provider),
) -> FuelService:
    """Build the fuel layer service."""
    return FuelService(provider=provider, session=session)


def get_truck_restriction_service(
    session: SessionDep,
    provider: TruckRestrictionProvider = Depends(get_truck_restriction_provider),
) -> TruckRestrictionService:
    """Build the truck restriction layer service."""
    return TruckRestrictionService(provider=provider, session=session)


def get_rest_area_service(
    session: SessionDep,
    provider: RestAreaProvider = Depends(get_rest_area_provider),
) -> HerePoiService:
    """Build the rest area layer service."""
    return HerePoiService(provider=provider, session=session)


def get_map_layer_service(
    geocoding_service: GeocodingService = Depends(get_geocoding_service),
    routing_service: RoutingService = Depends(get_routing_service),
    traffic_service: TrafficService = Depends(get_traffic_service),
    fuel_service: FuelService = Depends(get_fuel_service),
    truck_restriction_service: TruckRestrictionService = Depends(
        get_truck_restriction_service
    ),
    rest_area_service: HerePoiService = Depends(get_rest_area_service),
) -> MapLayerService:
    """Build the map layer orchestrator."""
    return MapLayerService(
        geocoding_service,
        routing_service,
        traffic_service,
        fuel_service,
        truck_restriction_service,
        rest_area_service,
    )


MapLayerServiceDep = Annotated[MapLayerService, Depends(get_map_layer_service)]
