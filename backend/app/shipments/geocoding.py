"""Resolving extracted stop addresses into coordinates.

A stop that cannot be geocoded must not sink the whole document: the rest of
the extraction is still worth keeping, and a dispatcher can correct the address
by hand in the review screen. Every failure is therefore recorded per stop.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from app.geocoding.service import GeocodingService
from app.providers.exceptions import ProviderError
from app.providers.geo import GeoJSONPoint
from app.shipments.extraction.schemas import ExtractedStop

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GeocodedStop:
    """The outcome of geocoding a single extracted stop."""

    location: GeoJSONPoint | None
    geocoded_address: str | None
    error: str | None

    @property
    def is_resolved(self) -> bool:
        return self.location is not None


async def geocode_stops(
    stops: list[ExtractedStop],
    *,
    service: GeocodingService,
) -> list[GeocodedStop]:
    """Geocode every stop, returning one result per stop in the same order.

    Stops are resolved sequentially rather than concurrently so that repeated
    addresses benefit from the cache writes of earlier stops and so that a
    multi-stop load cannot burst through the provider's rate limit.
    """
    results: list[GeocodedStop] = []
    for stop in stops:
        results.append(await _geocode_stop(stop, service=service))
    return results


async def _geocode_stop(
    stop: ExtractedStop,
    *,
    service: GeocodingService,
) -> GeocodedStop:
    address = stop.address.strip()
    if not address:
        return GeocodedStop(
            location=None,
            geocoded_address=None,
            error="The document did not provide an address for this stop.",
        )

    try:
        result = await service.search(address)
    except ProviderError as exc:
        logger.warning(
            "Shipment stop could not be geocoded",
            sequence=stop.sequence,
            error=str(exc),
        )
        return GeocodedStop(location=None, geocoded_address=None, error=str(exc))

    return GeocodedStop(
        location=result.location,
        geocoded_address=result.formatted_address,
        error=None,
    )
