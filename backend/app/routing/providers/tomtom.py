"""
TomTom routing provider (compatibility shim).
The implementation moved to :mod:`app.providers.tomtom.routing` when TomTom was
split into per-domain adapters. ``TomTomProvider`` remains as an alias so that
existing imports and test patches keep working.
"""

from app.providers.tomtom.routing import TomTomRoutingProvider

TomTomProvider = TomTomRoutingProvider
__all__ = ["TomTomProvider", "TomTomRoutingProvider"]
