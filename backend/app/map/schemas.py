"""
Map overview schemas.

Request and response models for the aggregated map endpoint. Each layer is
independent: a failing optional layer yields ``null`` / an empty list plus an
entry in ``errors`` instead of failing the whole request.
"""

import uuid
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from app.core.config import settings
from app.geocoding.schemas import MapPointInput
from app.providers.geo import GeoJSONPoint
from app.providers.schemas import (
    FuelStationData,
    RestAreaData,
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
    REST_AREAS = "rest_areas"


class LayerError(BaseModel):
    """Non-fatal failure of a single layer."""

    layer: MapLayer
    provider: str | None = None
    message: str


class RouteLayerData(BaseModel):
    """Route layer payload."""

    id: uuid.UUID | None = None
    provider: str
    routes: list[Route]


class ConfiguredLayerProviders(BaseModel):
    """Configured provider names for each overview layer."""

    route: str
    traffic: str
    fuel: str
    truck_restrictions: str
    rest_areas: str


class RestAreaFeatureProperties(BaseModel):
    """Properties attached to each rest area GeoJSON feature."""

    provider: str
    provider_place_id: str
    title: str
    result_type: str | None = None
    categories: list[dict] = Field(default_factory=list)
    distance_meters: float | None = None
    address: dict | None = None
    access_points: list[dict] = Field(default_factory=list)
    opening_hours: list[dict] = Field(default_factory=list)
    contacts: list[dict] = Field(default_factory=list)
    chains: list[dict] = Field(default_factory=list)
    references: list[dict] = Field(default_factory=list)
    metadata: dict | None = None


class RestAreaFeature(BaseModel):
    """GeoJSON point feature for a rest area."""

    type: str = "Feature"
    id: str
    properties: RestAreaFeatureProperties
    geometry: GeoJSONPoint


class RestAreaFeatureCollection(BaseModel):
    """GeoJSON feature collection for the rest_areas layer."""

    type: str = "FeatureCollection"
    features: list[RestAreaFeature] = Field(default_factory=list)


def build_rest_area_feature_collection(
    rest_areas: list[RestAreaData],
) -> RestAreaFeatureCollection:
    """Convert normalized rest areas into frontend-facing GeoJSON."""
    features = [
        RestAreaFeature(
            id=item.provider_place_id,
            properties=RestAreaFeatureProperties(
                provider=item.provider,
                provider_place_id=item.provider_place_id,
                title=item.title,
                result_type=item.result_type,
                categories=[cat.model_dump(mode="json") for cat in item.categories],
                distance_meters=item.distance_meters,
                address=(
                    item.address.model_dump(mode="json")
                    if item.address is not None
                    else None
                ),
                access_points=[p.model_dump(mode="json") for p in item.access_points],
                opening_hours=item.opening_hours,
                contacts=item.contacts,
                chains=[chain.model_dump(mode="json") for chain in item.chains],
                references=[ref.model_dump(mode="json") for ref in item.references],
                metadata={
                    **({"ontologyId": item.ontology_id} if item.ontology_id else {}),
                    **(item.metadata or {}),
                }
                or None,
            ),
            geometry=item.position,
        )
        for item in rest_areas
    ]
    return RestAreaFeatureCollection(features=features)


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
        le=settings.MAP_LAYER_RESULT_LIMIT,
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
    configured_providers: ConfiguredLayerProviders
    traffic: TrafficLayerData | None = None
    fuel_stations: list[FuelStationData] = Field(default_factory=list)
    truck_restrictions: list[TruckRestrictionData] = Field(default_factory=list)
    rest_areas: RestAreaFeatureCollection = Field(
        default_factory=RestAreaFeatureCollection
    )
    errors: list[LayerError] = Field(default_factory=list)
