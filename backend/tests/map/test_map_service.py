"""
Tests for MapLayerService.

Covers concurrent layer resolution, partial degradation on optional layer
failures and propagation of mandatory route failures.
"""

import pytest

from app.geocoding.schemas import MapPointInput
from app.map.schemas import MapLayer, MapOverviewRequest
from app.map.service import MapLayerService
from app.providers.exceptions import ProviderUnavailableError
from app.providers.geo import GeoJSONPoint
from app.providers.schemas import (
    FuelStationData,
    RestAreaCategory,
    RestAreaData,
    TrafficLayerData,
    TruckRestrictionData,
)
from app.routing.exceptions import RoutingNoRouteFoundError
from app.routing.schemas import (
    CalculateRouteRequest,
    CalculateRouteResponse,
    RoutePlanningLocations,
)

ROUTE_RESPONSE = {
    "routes": [
        {
            "summary": {"lengthInMeters": 1000, "travelDurationInSeconds": 60},
            "legs": [
                {
                    "summary": {
                        "lengthInMeters": 1000,
                        "travelDurationInSeconds": 60,
                    },
                    "path": {
                        "type": "LineString",
                        "coordinates": [[-74.006, 40.7128], [-73.9855, 40.758]],
                    },
                }
            ],
        }
    ]
}


def build_request() -> MapOverviewRequest:
    """Build a minimal map overview request."""
    return MapOverviewRequest(
        route=CalculateRouteRequest(
            route_planning_locations=RoutePlanningLocations(
                origin=GeoJSONPoint(coordinates=(-74.006, 40.7128)),
                destination=GeoJSONPoint(coordinates=(-73.9855, 40.758)),
            )
        )
    )


class FakeRoutingService:
    """Routing service stub."""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls: list[dict] = []

    async def calculate_route(self, request, *, force_refresh=False):
        """Return a canned response or raise the configured error."""
        self.calls.append({"request": request, "force_refresh": force_refresh})
        if self.error is not None:
            raise self.error
        return CalculateRouteResponse.model_validate(self.response)


class FakeGeocodingService:
    """Geocoding service stub."""

    def __init__(self, mapping: dict[str, GeoJSONPoint] | None = None):
        self.mapping = mapping or {}
        self.calls: list[dict] = []

    async def normalize_point(
        self, point: MapPointInput, *, force_refresh: bool = False
    ):
        self.calls.append({"point": point, "force_refresh": force_refresh})
        if point.location is not None:
            return point.location
        assert point.address is not None
        return self.mapping[point.address]


class FakeTrafficService:
    """Traffic service stub."""

    def __init__(self, data=None, error=None):
        self.data = data
        self.error = error
        self.calls: list[bool] = []

    async def get_traffic(self, query, *, force_refresh=False):
        """Return canned traffic data or raise."""
        self.calls.append(force_refresh)
        if self.error is not None:
            raise self.error
        return self.data


class FakeFuelService:
    """Fuel service stub."""

    def __init__(self, data=None, error=None):
        self.data = data or []
        self.error = error
        self.calls: list[bool] = []

    async def find_stations(self, query, *, force_refresh=False):
        """Return canned stations or raise."""
        self.calls.append(force_refresh)
        if self.error is not None:
            raise self.error
        return self.data


class FakeTruckService:
    """Truck restriction service stub."""

    def __init__(self, data=None, error=None):
        self.data = data or []
        self.error = error
        self.calls: list[bool] = []

    async def find_restrictions(self, query, *, force_refresh=False):
        """Return canned restrictions or raise."""
        self.calls.append(force_refresh)
        if self.error is not None:
            raise self.error
        return self.data


class FakeRestAreaService:
    """Rest area service stub."""

    def __init__(self, data=None, error=None):
        self.data = data or []
        self.error = error
        self.calls: list[bool] = []

    async def find_rest_areas(self, query, *, force_refresh=False):
        """Return canned rest areas or raise."""
        self.calls.append(force_refresh)
        if self.error is not None:
            raise self.error
        return self.data


def build_service(
    geocoding=None,
    routing=None,
    traffic=None,
    fuel=None,
    truck=None,
    rest_areas=None,
) -> MapLayerService:
    """Assemble a MapLayerService from stubs."""
    return MapLayerService(  # type: ignore[arg-type]
        geocoding_service=(geocoding or FakeGeocodingService()),  # type: ignore[arg-type]
        routing_service=(routing or FakeRoutingService(response=ROUTE_RESPONSE)),  # type: ignore[arg-type]
        traffic_service=(
            traffic or FakeTrafficService(data=TrafficLayerData(provider="tomtom"))
        ),
        fuel_service=(fuel or FakeFuelService()),  # type: ignore[arg-type]
        truck_restriction_service=(truck or FakeTruckService()),  # type: ignore[arg-type]
        rest_area_service=(rest_areas or FakeRestAreaService()),  # type: ignore[arg-type]
    )


class TestMapLayerServiceSuccess:
    """All layers resolve successfully."""

    @pytest.mark.asyncio
    async def test_returns_all_layers(self):
        """Every layer is present and errors are empty."""
        station = FuelStationData(
            external_id="s1",
            name="Pilot",
            location=GeoJSONPoint(coordinates=(-74.0, 40.72)),
        )
        restriction = TruckRestrictionData(
            external_id="r1",
            location=GeoJSONPoint(coordinates=(-74.0, 40.73)),
        )
        rest_area = RestAreaData(
            provider="here",
            provider_place_id="here:pds:place:r1",
            title="O'Hare Oasis Travel Plaza",
            position=GeoJSONPoint(coordinates=(-74.0, 40.731)),
            categories=[
                RestAreaCategory(
                    id="700-7900-0131",
                    name="Truck Parking",
                    primary=True,
                )
            ],
        )
        service = build_service(
            fuel=FakeFuelService(data=[station]),
            truck=FakeTruckService(data=[restriction]),
            rest_areas=FakeRestAreaService(data=[rest_area]),
        )

        result = await service.get_overview(build_request())

        assert result.route is not None
        assert result.route.provider == "tomtom"
        assert len(result.route.routes) == 1
        assert result.traffic is not None
        assert [s.external_id for s in result.fuel_stations] == ["s1"]
        assert [r.external_id for r in result.truck_restrictions] == ["r1"]
        assert len(result.rest_areas.features) == 1
        assert (
            result.rest_areas.features[0].properties.provider_place_id
            == "here:pds:place:r1"
        )
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_layer_subset_skips_other_layers(self):
        """Only requested layers are resolved."""
        service = build_service(
            traffic=FakeTrafficService(error=AssertionError("must not run")),
        )
        request = build_request()
        request.layers = [MapLayer.FUEL]

        result = await service.get_overview(request)

        assert result.traffic is None
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_route_overview_accepts_addresses(self):
        """Address inputs are normalized before routing."""
        geocoding = FakeGeocodingService(
            mapping={
                "pickup address": GeoJSONPoint(coordinates=(-96.6705, 33.1032)),
                "delivery address": GeoJSONPoint(coordinates=(-123.0463, 44.0860)),
            }
        )
        routing = FakeRoutingService(response=ROUTE_RESPONSE)
        service = build_service(geocoding=geocoding, routing=routing)

        result = await service.get_overview(
            MapOverviewRequest(
                pickup=MapPointInput(address="pickup address"),
                delivery=MapPointInput(address="delivery address"),
            )
        )

        assert result.route is not None
        assert len(geocoding.calls) == 2
        normalized_request = routing.calls[0]["request"]
        assert normalized_request.route_planning_locations.origin.coordinates == (
            -96.6705,
            33.1032,
        )
        assert normalized_request.route_planning_locations.destination.coordinates == (
            -123.0463,
            44.0860,
        )

    @pytest.mark.asyncio
    async def test_route_overview_accepts_mixed_inputs(self):
        """Address + coordinate input is supported."""
        geocoding = FakeGeocodingService(
            mapping={
                "pickup address": GeoJSONPoint(coordinates=(-96.6705, 33.1032)),
            }
        )
        routing = FakeRoutingService(response=ROUTE_RESPONSE)
        service = build_service(geocoding=geocoding, routing=routing)

        await service.get_overview(
            MapOverviewRequest(
                pickup=MapPointInput(address="pickup address"),
                delivery=MapPointInput(
                    location=GeoJSONPoint(coordinates=(-123.0463, 44.086))
                ),
            )
        )

        assert len(geocoding.calls) == 2
        assert geocoding.calls[1]["point"].location is not None

    @pytest.mark.asyncio
    async def test_force_refresh_propagates_to_all_services(self):
        """force_refresh bypasses geocoding and downstream caches."""
        geocoding = FakeGeocodingService(
            mapping={
                "pickup address": GeoJSONPoint(coordinates=(-96.6705, 33.1032)),
                "delivery address": GeoJSONPoint(coordinates=(-123.0463, 44.0860)),
            }
        )
        routing = FakeRoutingService(response=ROUTE_RESPONSE)
        traffic = FakeTrafficService(data=TrafficLayerData(provider="tomtom"))
        fuel = FakeFuelService()
        truck = FakeTruckService()
        rest_areas = FakeRestAreaService()
        service = build_service(
            geocoding=geocoding,
            routing=routing,
            traffic=traffic,
            fuel=fuel,
            truck=truck,
            rest_areas=rest_areas,
        )

        await service.get_overview(
            MapOverviewRequest(
                pickup=MapPointInput(address="pickup address"),
                delivery=MapPointInput(address="delivery address"),
            ),
            force_refresh=True,
        )

        assert all(call["force_refresh"] for call in geocoding.calls)
        assert routing.calls[0]["force_refresh"] is True
        assert traffic.calls == [True]
        assert fuel.calls == [True]
        assert truck.calls == [True]
        assert rest_areas.calls == [True]


class TestMapLayerServiceDegradation:
    """Optional layers degrade without failing the request."""

    @pytest.mark.asyncio
    async def test_traffic_failure_is_reported_as_error(self):
        """A failing traffic layer yields null plus an error entry."""
        service = build_service(
            traffic=FakeTrafficService(
                error=ProviderUnavailableError("down", provider="tomtom")
            )
        )

        result = await service.get_overview(build_request())

        assert result.route is not None
        assert result.traffic is None
        assert result.rest_areas.features == []
        assert len(result.errors) == 1
        assert result.errors[0].layer == MapLayer.TRAFFIC
        assert result.errors[0].provider == "tomtom"
        assert result.errors[0].message == "down"

    @pytest.mark.asyncio
    async def test_multiple_layer_failures_are_all_reported(self):
        """Independent failures accumulate in errors."""
        service = build_service(
            fuel=FakeFuelService(
                error=ProviderUnavailableError("no fuel api", provider="internal")
            ),
            truck=FakeTruckService(
                error=ProviderUnavailableError("no truck api", provider="internal")
            ),
            rest_areas=FakeRestAreaService(
                error=ProviderUnavailableError("no here api", provider="here")
            ),
        )

        result = await service.get_overview(build_request())

        failed = {error.layer for error in result.errors}
        assert failed == {
            MapLayer.FUEL,
            MapLayer.TRUCK_RESTRICTIONS,
            MapLayer.REST_AREAS,
        }
        assert result.fuel_stations == []
        assert result.truck_restrictions == []
        assert result.rest_areas.features == []
        assert result.traffic is not None

    @pytest.mark.asyncio
    async def test_unexpected_exception_is_captured(self):
        """Non-provider exceptions are also reported per layer."""
        service = build_service(fuel=FakeFuelService(error=ValueError("boom")))

        result = await service.get_overview(build_request())

        assert len(result.errors) == 1
        assert result.errors[0].layer == MapLayer.FUEL
        assert result.errors[0].message == "boom"


class TestMapLayerServiceRouteFailure:
    """The route layer is mandatory."""

    @pytest.mark.asyncio
    async def test_route_error_propagates(self):
        """A routing failure aborts the whole overview."""
        service = build_service(
            routing=FakeRoutingService(
                error=RoutingNoRouteFoundError("no route", provider="tomtom")
            )
        )

        with pytest.raises(RoutingNoRouteFoundError):
            await service.get_overview(build_request())

    @pytest.mark.asyncio
    async def test_route_without_geometry_skips_point_layers(self):
        """Point layers are skipped when the route has no usable geometry."""
        service = build_service(
            routing=FakeRoutingService(
                response={
                    "routes": [
                        {
                            "summary": {
                                "lengthInMeters": 10,
                                "travelDurationInSeconds": 1,
                            }
                        }
                    ]
                }
            ),
            traffic=FakeTrafficService(error=AssertionError("must not run")),
        )

        result = await service.get_overview(build_request())

        assert result.route is not None
        assert result.traffic is None
        assert result.fuel_stations == []
        assert result.rest_areas.features == []
        assert result.errors == []
