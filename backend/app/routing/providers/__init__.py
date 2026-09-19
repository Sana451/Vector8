"""
Routing providers module.
Implementations now live in :mod:`app.providers`; this package keeps
backward-compatible aliases.
Attributes are resolved lazily (PEP 562) because the adapters import
``app.routing.exceptions``, which would otherwise create an import cycle.
"""

from typing import Any

__all__ = ["RoutingProvider", "TomTomProvider"]


def __getattr__(name: str) -> Any:
    """Lazily resolve re-exported provider symbols."""
    if name == "RoutingProvider":
        from app.providers.base import RoutingProvider

        return RoutingProvider
    if name == "TomTomProvider":
        from app.providers.tomtom.routing import TomTomRoutingProvider

        return TomTomRoutingProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
