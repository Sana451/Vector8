"""
No-op traffic provider.

Returns empty traffic data without making any API calls.
Useful for development and testing to conserve API tokens.
"""

from datetime import UTC, datetime

from app.providers.schemas import LayerQuery, TrafficLayerData


class OffTrafficProvider:
    """Traffic provider that returns no incidents.

    When TRAFFIC_PROVIDER=off, this provider is used instead of TomTom
    to avoid consuming API quota during development.
    """

    async def get_traffic(self, query: LayerQuery) -> TrafficLayerData:
        """Return empty traffic data.

        Args:
            query: Corridor query (ignored).

        Returns:
            Empty traffic layer payload.
        """
        return TrafficLayerData(
            provider="off",
            incidents=[],
            total_delay_seconds=0,
            observed_at=datetime.now(UTC),
        )
