"""
Tests for MapLayerService.

Covers concurrent layer resolution, partial degradation on optional layer
failures and propagation of mandatory route failures.
"""

import pytest

from app.map.schemas import MapLayer, MapOverviewRequest
from app.map.service import MapLayerService
from app.providers.exceptions import ProviderUnavailableError
from app.providers.schemas import (
    FuelStationData,
    TrafficLayerData,
    TruckRestrictionData,
)
from app.routing.exceptions import RoutingNoRouteFoundError
from app.routing.schemas import CalculateRouteResponse

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
        route={
            "route_planning_locations": {
                "origin": {"type": "Point", "coordinates": [-74.006, 40.7128]},
                "destination": {"type": "Point", "coordinates": [-73.9855, 40.758]},
            }
        }
    )


class FakeRoutingService:
    """Routing service stub."""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    async def calculate_route(self, request, *, force_refresh=False):
        """Return a canned response or raise the configured error."""
        if self.error is not None:
            raise self.error
        return CalculateRouteResponse.model_validate(self.response)


class FakeTrafficService:
    """Traffic service stub."""

    def __init__(self, data=None, error=None):
        self.data = data
        self.error = error

    async def get_traffic(self, query, *, force_refresh=False):
        """Return canned traffic data or raise."""
        if self.error is not None:
            raise self.error
        return self.data


class FakeFuelService:
    """Fuel service stub."""

    def __init__(self, data=None, error=None):
        self.data = data or []
        self.error = error

    async def find_stations(self, query, *, force_refresh=False):
        """Return canned stations or raise."""
        if self.error is not None:
            raise self.error
        return self.data


class FakeTruckService:
    """Truck restriction service stub."""

    def __init__(self, data=None, error=None):
        self.data = data or []
        self.error = error

    async def find_restrictions(self, query, *, force_refresh=False):
        """Return canned restrictions or raise."""
        if self.error is not None:
            raise self.error
        return self.data


def build_service(
    routing=None,
    traffic=None,
    fuel=None,
    truck=None,
) -> MapLayerService:
    """Assemble a MapLayerService from stubs."""
    return MapLayerService(
        routing_service=routing or FakeRoutingService(response=ROUTE_RESPONSE),
        traffic_service=traffic
        or FakeTrafficService(data=TrafficLayerData(provider="tomtom")),
        fuel_service=fuel or FakeFuelService(),
        truck_restriction_service=truck or FakeTruckService(),
    )


class TestMapLayerServiceSuccess:
    """All layers resolve successfully."""

    @pytest.mark.asyncio
    async def test_returns_all_layers(self):
        """Every layer is present and errors are empty."""
        station = FuelStationData(
            external_id="s1",
            name="Pilot",
            location={"type": "Point", "coordinates": [-74.0, 40.72]},
        )
        restriction = TruckRestrictionData(
            external_id="r1",
            location={"type": "Point", "coordinates": [-74.0, 40.73]},
        )
        service = build_service(
            fuel=FakeFuelService(data=[station]),
            truck=FakeTruckService(data=[restriction]),
        )

        result = await service.get_overview(build_request())

        assert result.route is not None
        assert result.route.provider == "tomtom"
        assert len(result.route.routes) == 1
        assert result.traffic is not None
        assert [s.external_id for s in result.fuel_stations] == ["s1"]
        assert [r.external_id for r in result.truck_restrictions] == ["r1"]
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
        )

        result = await service.get_overview(build_request())

        failed = {error.layer for error in result.errors}
        assert failed == {MapLayer.FUEL, MapLayer.TRUCK_RESTRICTIONS}
        assert result.fuel_stations == []
        assert result.truck_restrictions == []
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
        assert result.errors == []
