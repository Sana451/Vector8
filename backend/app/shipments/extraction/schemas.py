"""Structured shape the language model must return for a shipping document.

These are extraction-time models, deliberately separate from both the
persistence models and the API schemas: they describe what a broker document
can say, not what the application stores or exposes.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from app.shipments.domain import StopKind

MAX_STOPS = 50


class ExtractedStop(BaseModel):
    """One pickup or dropoff as written in the document."""

    sequence: int = Field(ge=1, description="1-based order the stop is served in")
    kind: StopKind
    company_name: str | None = None
    address: str = Field(
        min_length=1,
        max_length=512,
        description="Full street address including city, state and ZIP",
    )
    scheduled_at_start: str | None = Field(
        default=None, description="ISO 8601 local time, or null when absent"
    )
    scheduled_at_end: str | None = Field(
        default=None, description="ISO 8601 local time closing the window"
    )
    reference_number: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    notes: str | None = None


class ShipmentExtraction(BaseModel):
    """Everything the parser pulls out of one rate confirmation."""

    broker_name: str | None = None
    broker_contact: str | None = Field(
        default=None, description="Dispatcher name, phone or email at the broker"
    )
    reference_number: str | None = Field(
        default=None, description="Load number or PRO number identifying the order"
    )
    total_weight_lbs: Decimal | None = Field(default=None, ge=0)
    rate_total: Decimal | None = Field(default=None, ge=0)
    rate_currency: str | None = Field(default=None, max_length=8)
    equipment_type: str | None = Field(
        default=None, description="Trailer or truck type as written in the document"
    )
    notes: str | None = Field(
        default=None, description="Carrier instructions worth keeping"
    )
    stops: list[ExtractedStop] = Field(default_factory=list, max_length=MAX_STOPS)
    extras: dict[str, str] = Field(
        default_factory=dict,
        description="Anything else worth keeping that has no dedicated field",
    )
    field_confidence: dict[str, float] = Field(
        default_factory=dict,
        description="Per-field confidence from 0 to 1, keyed by field name",
    )
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
