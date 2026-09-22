"""
Provider registry.

Maps ``(domain, name)`` pairs onto adapter factories so that each map layer can
be backed by a different vendor without touching business logic.

Example:
    >>> registry.get("routing", "tomtom")
    >>> registry.get("traffic", "tomtom")
    >>> registry.get("fuel", "internal")
"""

from collections.abc import Callable
from typing import Any, Literal

from app.providers.exceptions import ProviderNotRegisteredError

Domain = Literal[
    "geocoding",
    "routing",
    "traffic",
    "fuel",
    "truck_restrictions",
    "rest_areas",
]

ProviderFactory = Callable[[], Any]


class ProviderRegistry:
    """Registry of provider factories keyed by ``(domain, name)``."""

    def __init__(self) -> None:
        self._factories: dict[tuple[str, str], ProviderFactory] = {}

    def register(
        self,
        domain: Domain,
        name: str,
        factory: ProviderFactory,
    ) -> None:
        """Register a provider factory.

        Args:
            domain: Layer domain.
            name: Provider name as used in settings.
            factory: Zero-argument callable returning an adapter instance.

        Note:
            Registration happens at import time and must stay free of logging
            side effects: stdout is consumed by the OpenAPI generation script.
        """
        self._factories[(domain, name)] = factory

    def get(self, domain: Domain, name: str) -> Any:
        """Instantiate a registered provider.

        Args:
            domain: Layer domain.
            name: Provider name as used in settings.

        Returns:
            Adapter instance.

        Raises:
            ProviderNotRegisteredError: If no factory matches the pair.
        """
        factory = self._factories.get((domain, name))
        if factory is None:
            supported = ", ".join(sorted(self.available(domain))) or "none"
            raise ProviderNotRegisteredError(
                f"Unsupported {domain} provider: {name}. Supported: {supported}",
                provider=name,
            )
        return factory()

    def available(self, domain: Domain) -> list[str]:
        """List provider names registered for a domain.

        Args:
            domain: Layer domain.

        Returns:
            Sorted list of provider names.
        """
        return sorted(name for (d, name) in self._factories if d == domain)


registry = ProviderRegistry()


def _register_defaults() -> None:
    """Register built-in adapters.

    Imports are local to keep module import order free of cycles: adapters
    import schemas from :mod:`app.providers`, which must be fully initialized.
    """
    from app.geocoding.providers.tomtom import TomTomGeocodingProvider
    from app.providers.fuel.internal import InternalFuelStationProvider
    from app.providers.here.poi import HerePoiProvider
    from app.providers.tomtom.routing import TomTomRoutingProvider
    from app.providers.tomtom.traffic import TomTomTrafficProvider
    from app.providers.traffic.off import OffTrafficProvider
    from app.providers.truck_restrictions.internal import (
        InternalTruckRestrictionProvider,
    )

    registry.register("geocoding", "tomtom", TomTomGeocodingProvider)
    registry.register("routing", "tomtom", TomTomRoutingProvider)
    registry.register("traffic", "tomtom", TomTomTrafficProvider)
    registry.register("traffic", "off", OffTrafficProvider)
    registry.register("fuel", "internal", InternalFuelStationProvider)
    registry.register(
        "truck_restrictions", "internal", InternalTruckRestrictionProvider
    )
    registry.register("rest_areas", "here", HerePoiProvider)


_register_defaults()
