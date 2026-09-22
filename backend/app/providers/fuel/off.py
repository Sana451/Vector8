"""
No-op fuel provider.

Returns an empty fuel station list without making any external API calls.
Useful for development, testing and deployments where fuel data is disabled.
"""

from app.providers.schemas import FuelStationData, LayerQuery


class OffFuelProvider:
    """Fuel provider that returns no stations."""

    async def find_stations(self, query: LayerQuery) -> list[FuelStationData]:
        """Return an empty fuel station list.

        Args:
            query: Corridor query (ignored).

        Returns:
            Empty fuel station list.
        """
        return []
