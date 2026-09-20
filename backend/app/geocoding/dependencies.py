"""Dependency wiring for the geocoding domain."""

from typing import Annotated

from fastapi import Depends

from app.api.deps import SessionDep
from app.core.config import settings
from app.geocoding.providers.base import GeocodingProvider
from app.geocoding.service import GeocodingService
from app.providers.registry import registry


def get_geocoding_provider() -> GeocodingProvider:
    """Resolve the configured geocoding provider."""
    return registry.get("geocoding", settings.GEOCODING_PROVIDER)


def get_geocoding_service(
    session: SessionDep,
    provider: GeocodingProvider = Depends(get_geocoding_provider),
) -> GeocodingService:
    """Build the geocoding service."""
    return GeocodingService(provider=provider, session=session)


GeocodingServiceDep = Annotated[GeocodingService, Depends(get_geocoding_service)]
