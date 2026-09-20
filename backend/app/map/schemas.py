"""
Map overview schemas.

Request and response models for the aggregated map endpoint. Each layer is
independent: a failing optional layer yields ``null`` / an empty list plus an
entry in ``errors`` instead of failing the whole request.
"""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from app.geocoding.schemas import MapPointInput
from app.providers.schemas import (
    FuelStationData,
    TrafficLayerData,
    TruckRestrictionData,
)
from app.routing.schemas import CalculateRouteRequest, Route


class MapLayer(StrEnum):
    """Identifiers of the map layers."""

    ROUTE = "route"
    TRAFFIC = "traffic"
    FUEL = "fuel"
    TRUCK_RESTRICTIONS = "truck_restrictions"


class LayerError(BaseModel):
    """Non-fatal failure of a single layer."""

    layer: MapLayer
    provider: str | None = None
    message: str


class RouteLayerData(BaseModel):
    """Route layer payload."""

    provider: str
    routes: list[Route]


class MapOverviewRequest(BaseModel):
    """Aggregated map overview request.

    Supports two request shapes:
    - new format: ``pickup`` / ``delivery`` with either address or coordinates;
    - legacy format: ``route`` with a full ``CalculateRouteRequest``.
    """

    pickup: MapPointInput | None = Field(
        default=None,
        description="Pickup point, either by address or GeoJSON coordinates",
    )
    delivery: MapPointInput | None = Field(
        default=None,
        description="Delivery point, either by address or GeoJSON coordinates",
    )
    route: CalculateRouteRequest | None = Field(
        default=None,
        description="Legacy route calculation request kept for backward compatibility",
    )
    radius_meters: int | None = Field(
        default=None,
        ge=1,
        le=100_000,
        description="Corridor radius for point layers (defaults to settings)",
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        le=1000,
        description="Maximum features per point layer (defaults to settings)",
    )
    layers: list[MapLayer] | None = Field(
        default=None,
        description="Subset of layers to resolve; all layers when omitted",
    )

    @model_validator(mode="after")
    def validate_route_shape(self) -> MapOverviewRequest:
        has_legacy_route = self.route is not None
        has_modern_points = self.pickup is not None or self.delivery is not None

        if has_legacy_route and has_modern_points:
            raise ValueError(
                "Provide either legacy route or pickup/delivery, not both."
            )

        if has_legacy_route:
            return self

        if self.pickup is None or self.delivery is None:
            raise ValueError(
                "Either legacy route or both pickup and delivery must be provided."
            )

        return self


class MapOverviewResponse(BaseModel):
    """Aggregated map overview response.

    ``route`` is mandatory: if routing fails the endpoint returns 502. Every
    other layer degrades gracefully.
    """

    route: RouteLayerData | None = None
    traffic: TrafficLayerData | None = None
    fuel_stations: list[FuelStationData] = Field(default_factory=list)
    truck_restrictions: list[TruckRestrictionData] = Field(default_factory=list)
    errors: list[LayerError] = Field(default_factory=list)
