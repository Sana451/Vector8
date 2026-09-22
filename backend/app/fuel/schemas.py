"""Schemas for admin fuel imports."""

from pydantic import BaseModel, Field


class PumpPriceImportRequest(BaseModel):
    """Admin request for synchronously importing PumpPrice stations."""

    fuel_analytics_session: str = Field(
        min_length=1,
        description="Value of the _fuel_analytics_session cookie",
    )


class PumpPriceImportResponse(BaseModel):
    """Summary of a synchronous PumpPrice import run."""

    source_provider: str = "pumpprice"
    persisted_provider: str = "internal"
    stations_received: int = Field(default=0, ge=0)
    unique_stations: int = Field(default=0, ge=0)
    duplicates_discarded: int = Field(default=0, ge=0)
    persisted_stations: int = Field(default=0, ge=0)
