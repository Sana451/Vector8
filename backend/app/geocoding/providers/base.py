"""Protocols for geocoding providers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from app.geocoding.schemas import GeocodingResult


@runtime_checkable
class GeocodingProvider(Protocol):
    """Resolves addresses into coordinates."""

    async def search(self, query: str) -> GeocodingResult:
        """Resolve a free-form query into a normalized geocoding result."""
        ...
