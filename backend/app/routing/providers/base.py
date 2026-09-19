"""
Routing provider abstraction (compatibility shim).
The canonical protocol now lives in :mod:`app.providers.base` alongside the
other map layer domains. This module re-exports it so that existing imports
keep working.
"""

from app.providers.base import RoutingProvider

__all__ = ["RoutingProvider"]
