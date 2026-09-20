"""
Tests for ProviderRegistry.

Covers registration, lookup, unknown provider handling and the built-in
default registrations.
"""

import pytest

from app.providers.exceptions import ProviderNotRegisteredError
from app.providers.registry import ProviderRegistry, registry


class TestProviderRegistry:
    """Registration and lookup behaviour."""

    def test_register_and_get_returns_instance(self):
        """A registered factory is invoked on get()."""
        local = ProviderRegistry()
        local.register("routing", "dummy", lambda: "instance")

        assert local.get("routing", "dummy") == "instance"

    def test_get_unknown_provider_raises(self):
        """Unknown provider names raise a descriptive error."""
        local = ProviderRegistry()
        local.register("routing", "dummy", lambda: "instance")

        with pytest.raises(ProviderNotRegisteredError) as exc_info:
            local.get("routing", "missing")

        assert "missing" in str(exc_info.value)
        assert "dummy" in str(exc_info.value)

    def test_domains_are_isolated(self):
        """The same provider name in another domain is not resolved."""
        local = ProviderRegistry()
        local.register("routing", "shared", lambda: "routing-instance")

        with pytest.raises(ProviderNotRegisteredError):
            local.get("traffic", "shared")

    def test_available_lists_only_domain_providers(self):
        """available() filters by domain and sorts names."""
        local = ProviderRegistry()
        local.register("traffic", "b", lambda: None)
        local.register("traffic", "a", lambda: None)
        local.register("fuel", "c", lambda: None)

        assert local.available("traffic") == ["a", "b"]
        assert local.available("fuel") == ["c"]

    def test_register_overrides_existing(self):
        """Re-registering a name replaces the previous factory."""
        local = ProviderRegistry()
        local.register("fuel", "internal", lambda: "old")
        local.register("fuel", "internal", lambda: "new")

        assert local.get("fuel", "internal") == "new"

    def test_get_creates_new_instance_per_call(self):
        """Factories are invoked per call, not cached."""
        local = ProviderRegistry()
        local.register("fuel", "internal", list)

        first = local.get("fuel", "internal")
        second = local.get("fuel", "internal")

        assert first is not second


class TestDefaultRegistrations:
    """Built-in adapters registered at import time."""

    @pytest.mark.parametrize(
        ("domain", "provider"),
        [
            ("geocoding", "tomtom"),
            ("routing", "tomtom"),
            ("traffic", "tomtom"),
            ("fuel", "internal"),
            ("truck_restrictions", "internal"),
        ],
    )
    def test_default_provider_is_registered(self, domain, provider):
        """Each domain exposes its default provider."""
        assert provider in registry.available(domain)

    def test_routing_default_implements_protocol(self):
        """The default routing adapter satisfies the RoutingProvider protocol."""
        provider = registry.get("routing", "tomtom")

        assert hasattr(provider, "calculate_route")

    def test_geocoding_default_implements_protocol(self):
        """The default geocoding adapter satisfies the GeocodingProvider protocol."""
        provider = registry.get("geocoding", "tomtom")

        assert hasattr(provider, "search")

    def test_traffic_default_implements_protocol(self):
        """The default traffic adapter satisfies the TrafficProvider protocol."""
        provider = registry.get("traffic", "tomtom")

        assert hasattr(provider, "get_traffic")

    def test_fuel_default_implements_protocol(self):
        """The default fuel adapter satisfies the FuelStationProvider protocol."""
        provider = registry.get("fuel", "internal")

        assert hasattr(provider, "find_stations")

    def test_truck_restriction_default_implements_protocol(self):
        """The default truck adapter satisfies its protocol."""
        provider = registry.get("truck_restrictions", "internal")

        assert hasattr(provider, "find_restrictions")
