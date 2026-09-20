"""Application service for geocoding and point normalization."""

from __future__ import annotations

from sqlmodel import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.geocoding.providers.base import GeocodingProvider
from app.geocoding.repository import GeocodingCacheRepository
from app.geocoding.schemas import GeocodingResult, MapPointInput
from app.providers.geo import GeoJSONPoint
from app.routing.hashing import compute_request_hash

logger = get_logger(__name__)


class GeocodingService:
    """Geocoding service with provider-backed caching."""

    def __init__(self, provider: GeocodingProvider, session: Session):
        self.provider = provider
        self.provider_name = settings.GEOCODING_PROVIDER
        self.repository = GeocodingCacheRepository(session)

    async def search(
        self,
        query: str,
        *,
        force_refresh: bool = False,
    ) -> GeocodingResult:
        normalized_query = query.strip()
        query_hash = compute_request_hash(
            {
                "provider": self.provider_name,
                "query": normalized_query.casefold(),
            }
        )

        if not force_refresh:
            cached = self.repository.get_valid(self.provider_name, query_hash)
            if cached is not None:
                logger.info(
                    "Geocoding cache hit",
                    provider=self.provider_name,
                    query_hash=query_hash,
                )
                return GeocodingResult.model_validate(cached.provider_response)

            logger.info(
                "Geocoding cache miss",
                provider=self.provider_name,
                query_hash=query_hash,
            )

        result = await self.provider.search(normalized_query)
        lon, lat = result.location.coordinates
        self.repository.upsert(
            provider=self.provider_name,
            query_hash=query_hash,
            query=normalized_query,
            formatted_address=result.formatted_address,
            longitude=lon,
            latitude=lat,
            provider_response=result.model_dump(mode="json"),
            ttl_seconds=settings.GEOCODING_CACHE_TTL_SECONDS,
        )
        return result

    async def normalize_point(
        self,
        point: MapPointInput,
        *,
        force_refresh: bool = False,
    ) -> GeoJSONPoint:
        if point.location is not None:
            logger.info(
                "Point already provided as coordinates",
                coordinates=point.location.coordinates,
            )
            return point.location

        result = await self.search(point.address or "", force_refresh=force_refresh)
        logger.info(
            "Point normalized from address",
            provider=self.provider_name,
            formatted_address=result.formatted_address,
        )
        return result.location
