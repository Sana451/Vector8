"""Geocoding request/response schemas and internal DTOs."""

from pydantic import BaseModel, Field, field_validator, model_validator

from app.providers.geo import GeoJSONPoint


class AddressInput(BaseModel):
    """Address-only input from API clients."""

    address: str = Field(min_length=1, description="Free-form postal address")

    @field_validator("address")
    @classmethod
    def validate_address(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Address must not be empty.")
        return value


class MapPointInput(BaseModel):
    """User-facing point input supporting either address or coordinates."""

    address: str | None = Field(default=None, description="Free-form postal address")
    location: GeoJSONPoint | None = Field(
        default=None, description="GeoJSON Point coordinates"
    )

    @field_validator("address")
    @classmethod
    def normalize_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def validate_exclusive_fields(self) -> MapPointInput:
        if (self.address is None) == (self.location is None):
            raise ValueError("Either address or location must be provided.")
        return self


class GeocodingResult(BaseModel):
    """Normalized geocoding result used inside the application."""

    formatted_address: str
    location: GeoJSONPoint
    provider_id: str | None = None


class GeocodingSearchRequest(BaseModel):
    """Public geocoding search request."""

    query: str = Field(min_length=1, description="Free-form address query")

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Query must not be empty.")
        return value


class GeocodingSearchResponse(BaseModel):
    """Public geocoding search response."""

    formatted_address: str
    location: GeoJSONPoint

    @classmethod
    def from_result(cls, result: GeocodingResult) -> GeocodingSearchResponse:
        return cls(
            formatted_address=result.formatted_address,
            location=result.location,
        )
