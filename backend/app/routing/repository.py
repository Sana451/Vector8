"""
Route calculation repository.

CRUD and query operations for RouteCalculation persistence.
"""

from datetime import timedelta

from sqlmodel import Session, select

from app.core.datetime import get_datetime_utc
from app.core.logging import get_logger
from app.routing.models import RouteCalculation

logger = get_logger(__name__)


class RouteCalculationRepository:
    """Repository for RouteCalculation entities."""

    def __init__(self, session: Session):
        """Initialize repository with database session.

        Args:
            session: SQLModel session for database operations.
        """
        self.session = session

    def get_by_id(self, route_id) -> RouteCalculation | None:
        """Get route calculation by primary key."""
        return self.session.get(RouteCalculation, route_id)

    def get_by_provider_and_hash(
        self,
        provider: str,
        request_hash: str,
    ) -> RouteCalculation | None:
        """Get route calculation by provider and request hash.

        Args:
            provider: Routing provider name.
            request_hash: SHA-256 hash of routing request.

        Returns:
            RouteCalculation if exists, None otherwise.
        """
        statement = select(RouteCalculation).where(
            (RouteCalculation.provider == provider)
            & (RouteCalculation.request_hash == request_hash)
        )
        return self.session.exec(statement).first()

    def get_valid_by_provider_and_hash(
        self,
        provider: str,
        request_hash: str,
    ) -> RouteCalculation | None:
        """Get valid (not expired) route calculation by provider and hash.

        Args:
            provider: Routing provider name.
            request_hash: SHA-256 hash of routing request.

        Returns:
            RouteCalculation if exists and not expired, None otherwise.
        """
        calculation = self.get_by_provider_and_hash(provider, request_hash)

        if not calculation:
            return None

        # Check if expired - compare timezone-aware datetimes
        now = get_datetime_utc()
        if calculation.expires_at < now:
            logger.info(
                "Route calculation cache expired",
                provider=provider,
                request_hash=request_hash,
                expires_at=calculation.expires_at,
            )
            return None

        return calculation

    def upsert_by_provider_and_hash(
        self,
        provider: str,
        request_hash: str,
        origin_wkt: str,
        destination_wkt: str,
        distance_meters: int,
        duration_seconds: int,
        request_data: dict,
        provider_response: dict,
        ttl_seconds: int,
        geometry_wkt: str | None = None,
    ) -> RouteCalculation:
        """Insert or update route calculation by provider and hash.

        Args:
            provider: Routing provider name.
            request_hash: SHA-256 hash of routing request.
            origin_wkt: Origin as WKT POINT.
            destination_wkt: Destination as WKT POINT.
            distance_meters: Route distance in meters.
            duration_seconds: Route duration in seconds.
            request_data: Serialized routing request.
            provider_response: Full provider API response.
            ttl_seconds: Time to live in seconds.
            geometry_wkt: Route geometry as WKT LINESTRING, optional.

        Returns:
            Persisted RouteCalculation (new or updated).

        Raises:
            Exception: Database operation failures.
        """
        try:
            existing = self.get_by_provider_and_hash(provider, request_hash)

            # Use timezone-aware UTC datetime for storage and comparison
            now = get_datetime_utc()
            expires_at = now + timedelta(seconds=ttl_seconds)

            if existing:
                # Update existing record
                logger.info(
                    "Updating route calculation",
                    provider=provider,
                    request_hash=request_hash,
                    id=existing.id,
                )

                existing.origin = origin_wkt
                existing.destination = destination_wkt
                existing.geometry = geometry_wkt
                existing.distance_meters = distance_meters
                existing.duration_seconds = duration_seconds
                existing.request_data = request_data
                existing.provider_response = provider_response
                existing.created_at = now
                existing.expires_at = expires_at

                self.session.add(existing)
                self.session.commit()
                self.session.refresh(existing)

                logger.info(
                    "Route calculation updated successfully",
                    id=existing.id,
                    provider=provider,
                )

                return existing
            else:
                # Create new record
                logger.info(
                    "Creating route calculation",
                    provider=provider,
                    request_hash=request_hash,
                )

                calculation = RouteCalculation(
                    provider=provider,
                    request_hash=request_hash,
                    origin=origin_wkt,
                    destination=destination_wkt,
                    geometry=geometry_wkt,
                    distance_meters=distance_meters,
                    duration_seconds=duration_seconds,
                    request_data=request_data,
                    provider_response=provider_response,
                    created_at=now,
                    expires_at=expires_at,
                )

                logger.info(
                    "RouteCalculation object created",
                    id=calculation.id,
                    distance_meters=distance_meters,
                    duration_seconds=duration_seconds,
                    geometry_size_bytes=len(geometry_wkt) if geometry_wkt else 0,
                )

                self.session.add(calculation)
                self.session.commit()
                self.session.refresh(calculation)

                logger.info(
                    "Route calculation created successfully",
                    id=calculation.id,
                    provider=provider,
                )

                return calculation

        except Exception as e:
            logger.error(
                "Error upserting route calculation",
                provider=provider,
                request_hash=request_hash,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            self.session.rollback()
            raise

    def delete_by_provider_and_hash(
        self,
        provider: str,
        request_hash: str,
    ) -> bool:
        """Delete route calculation by provider and hash.

        Args:
            provider: Routing provider name.
            request_hash: SHA-256 hash of routing request.

        Returns:
            True if deleted, False if not found.
        """
        calculation = self.get_by_provider_and_hash(provider, request_hash)

        if not calculation:
            return False

        self.session.delete(calculation)
        self.session.commit()

        logger.info(
            "Deleted route calculation",
            provider=provider,
            request_hash=request_hash,
        )

        return True
