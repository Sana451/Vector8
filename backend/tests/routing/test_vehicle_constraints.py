"""Tests for vehicle routing profile, HERE vehicle params and map integration."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.fleet.units import in_to_cm, lbs_to_kg, mph_to_mps
from app.map.schemas import MapOverviewRequest
from app.map.service import VehicleNotFoundError
from app.providers.geo import GeoJSONPoint
from app.providers.here.routing import HereRoutingProvider
from app.routing.hashing import compute_request_hash
from app.routing.schemas import (
    CalculateRouteRequest,
    RoutePlanningLocations,
    VehicleRoutingProfile,
)
from tests.map.test_map_service import (
    ROUTE_RESPONSE,
    FakeRoutingService,
    build_request,
    build_service,
)


def make_vehicle(**overrides) -> SimpleNamespace:
    data = {
        "vehicle_type": "truck",
        "height_in": 150,
        "width_in": 96,
        "length_in": 312,
        "gross_weight_lbs": 26000,
        "weight_per_axle_lbs": None,
        "axle_count": 2,
        "tires_count": 6,
        "trailer_count": 0,
        "trailer_length_in": None,
        "kpra_length_in": None,
        "payload_capacity_lbs": 8300,
        "max_speed_mph": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def route_request(vehicle: VehicleRoutingProfile | None = None):
    return CalculateRouteRequest(
        route_planning_locations=RoutePlanningLocations(
            origin=GeoJSONPoint(coordinates=(-74.006, 40.7128)),
            destination=GeoJSONPoint(coordinates=(-73.9855, 40.758)),
        ),
        vehicle=vehicle,
    )


class FakeVehicleRepository:
    def __init__(self, vehicle=None):
        self.vehicle = vehicle

    def get(self, vehicle_id):
        return self.vehicle


class TestUnits:
    def test_conversions(self) -> None:
        assert in_to_cm(150) == 381
        assert lbs_to_kg(26000) == 11793
        assert mph_to_mps(65) == 29.06
        assert in_to_cm(None) is None
        assert lbs_to_kg(None) is None
        assert mph_to_mps(None) is None


class TestVehicleRoutingProfile:
    def test_from_vehicle_converts_to_metric(self) -> None:
        profile = VehicleRoutingProfile.from_vehicle(make_vehicle())
        assert profile.vehicle_type == "StraightTruck"
        assert profile.height_cm == 381
        assert profile.width_cm == 244
        assert profile.gross_weight_kg == 11793
        assert profile.payload_capacity_kg == 3765
        assert profile.missing_recommended == []

    def test_tractor_type_and_missing_fields(self) -> None:
        profile = VehicleRoutingProfile.from_vehicle(
            make_vehicle(vehicle_type="tractor", height_in=None, gross_weight_lbs=None)
        )
        assert profile.vehicle_type == "Tractor"
        assert profile.missing_recommended == ["height", "gross_weight"]


class TestHereVehicleParams:
    def test_without_vehicle_params_are_unchanged(self) -> None:
        params = HereRoutingProvider()._build_params(route_request(), api_key="k")
        assert not any(key.startswith(("vehicle[", "truck[")) for key in params)

    def test_partial_profile_sends_only_set_values(self) -> None:
        profile = VehicleRoutingProfile.from_vehicle(
            make_vehicle(
                width_in=None, length_in=None, axle_count=None, tires_count=None
            )
        )
        params = HereRoutingProvider()._build_params(
            route_request(profile), api_key="k"
        )
        vehicle_params = {k: v for k, v in params.items() if k.startswith("vehicle[")}
        assert vehicle_params == {
            "vehicle[type]": "StraightTruck",
            "vehicle[height]": "381",
            "vehicle[grossWeight]": "11793",
            "vehicle[payloadCapacity]": "3765",
        }

    def test_trailer_count_sent_only_when_positive(self) -> None:
        with_trailer = VehicleRoutingProfile.from_vehicle(
            make_vehicle(vehicle_type="tractor", trailer_count=1, trailer_length_in=636)
        )
        params = HereRoutingProvider.vehicle_params(with_trailer)
        assert params["vehicle[type]"] == "Tractor"
        assert params["vehicle[trailerCount]"] == "1"
        assert params["vehicle[trailerLength]"] == "1615"
        assert "vehicle[trailerCount]" not in HereRoutingProvider.vehicle_params(
            VehicleRoutingProfile.from_vehicle(make_vehicle())
        )


class TestCacheHash:
    def test_vehicle_changes_hash(self) -> None:
        plain = route_request()
        with_vehicle = route_request(VehicleRoutingProfile.from_vehicle(make_vehicle()))
        assert compute_request_hash(
            plain.model_dump(mode="json", exclude={"vehicle"})
        ) != compute_request_hash(with_vehicle.model_dump(mode="json"))


class TestMapVehicleConstraints:
    @pytest.mark.asyncio
    async def test_applies_vehicle_and_reports_missing(self, monkeypatch) -> None:
        monkeypatch.setattr("app.map.service.settings.ROUTING_PROVIDER", "here")
        routing = FakeRoutingService(response=ROUTE_RESPONSE)
        service = build_service(routing=routing)
        service.vehicle_repository = FakeVehicleRepository(make_vehicle(height_in=None))
        request = build_request()
        request.vehicle_id = uuid.uuid4()

        response = await service.get_overview(request)

        sent = routing.calls[0]["request"]
        assert sent.vehicle is not None
        assert sent.vehicle.width_cm == 244
        info = response.vehicle_constraints
        assert info is not None and info.applied
        assert info.missing_fields == ["height"]
        assert info.sent_parameters["vehicle[width]"] == "244"

    @pytest.mark.asyncio
    async def test_checkbox_off_sends_nothing(self) -> None:
        routing = FakeRoutingService(response=ROUTE_RESPONSE)
        service = build_service(routing=routing)
        service.vehicle_repository = FakeVehicleRepository(make_vehicle())
        request = build_request()
        request.vehicle_id = uuid.uuid4()
        request.apply_vehicle_constraints = False

        response = await service.get_overview(request)

        assert routing.calls[0]["request"].vehicle is None
        assert response.vehicle_constraints is None

    @pytest.mark.asyncio
    async def test_unknown_vehicle_raises(self) -> None:
        service = build_service()
        service.vehicle_repository = FakeVehicleRepository(None)
        request = build_request()
        request.vehicle_id = uuid.uuid4()

        with pytest.raises(VehicleNotFoundError):
            await service.get_overview(request)

    def test_request_defaults(self) -> None:
        request = MapOverviewRequest.model_validate(
            {
                "pickup": {"address": "A"},
                "delivery": {"address": "B"},
            }
        )
        assert request.apply_vehicle_constraints is True
        assert request.vehicle_id is None
