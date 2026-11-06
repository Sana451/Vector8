"""Request and response schemas for the shipments API."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.providers.geo import GeoJSONPoint
from app.shipments.domain import DocumentParseStatus, PlanningStatus, StopKind


class ShipmentStopPublic(BaseModel):
    """A pickup or dropoff as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sequence: int
    kind: StopKind
    company_name: str | None = None
    address_raw: str
    location: GeoJSONPoint | None = None
    geocoded_address: str | None = None
    geocode_error: str | None = None
    scheduled_at_start: datetime | None = None
    scheduled_at_end: datetime | None = None
    reference_number: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    notes: str | None = None


class ShipmentStopWrite(BaseModel):
    """A stop as submitted by a dispatcher correcting an extraction.

    Coordinates are not accepted from the client: the address is the source of
    truth and the server geocodes it, so a corrected address can never drift
    away from the point used for routing.
    """

    kind: StopKind
    company_name: str | None = Field(default=None, max_length=255)
    address_raw: str = Field(min_length=1, max_length=512)
    scheduled_at_start: datetime | None = None
    scheduled_at_end: datetime | None = None
    reference_number: str | None = Field(default=None, max_length=128)
    contact_name: str | None = Field(default=None, max_length=255)
    contact_phone: str | None = Field(default=None, max_length=64)
    notes: str | None = None

    @field_validator("address_raw")
    @classmethod
    def validate_address(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A stop address must not be empty.")
        return value


class ShipmentDocumentPublic(BaseModel):
    """Document metadata; the bytes are served by a separate endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    content_sha256: str
    parse_status: DocumentParseStatus
    parse_error: str | None = None
    parsed_at: datetime | None = None
    uploaded_at: datetime


class ShipmentPublic(BaseModel):
    """A shipment in list responses, without stops or document bytes."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    planning_status: PlanningStatus
    broker_name: str | None = None
    reference_number: str | None = None
    total_weight_lbs: Decimal | None = None
    rate_total: Decimal | None = None
    rate_currency: str | None = None
    equipment_type: str | None = None
    extraction_confidence: Decimal | None = None
    is_manually_edited: bool
    created_at: datetime
    updated_at: datetime


class ShipmentDetailPublic(ShipmentPublic):
    """A shipment with everything needed by the review screen."""

    broker_contact: str | None = None
    notes: str | None = None
    extracted_payload: dict[str, Any] = Field(default_factory=dict)
    field_confidence: dict[str, Any] = Field(default_factory=dict)
    stops: list[ShipmentStopPublic] = Field(default_factory=list)
    documents: list[ShipmentDocumentPublic] = Field(default_factory=list)


class ShipmentsPublic(BaseModel):
    """A page of shipments."""

    data: list[ShipmentPublic]
    count: int


class ShipmentUpdateRequest(BaseModel):
    """A dispatcher's corrections to an extracted shipment.

    Omitted fields are left untouched. Passing ``stops`` replaces the whole
    list, because reordering and renumbering stops individually would let the
    sequence become inconsistent mid-request.
    """

    broker_name: str | None = Field(default=None, max_length=255)
    broker_contact: str | None = Field(default=None, max_length=512)
    reference_number: str | None = Field(default=None, max_length=128)
    total_weight_lbs: Decimal | None = Field(default=None, ge=0)
    rate_total: Decimal | None = Field(default=None, ge=0)
    rate_currency: str | None = Field(default=None, max_length=8)
    equipment_type: str | None = Field(default=None, max_length=128)
    notes: str | None = None
    planning_status: PlanningStatus | None = None
    stops: list[ShipmentStopWrite] | None = None


class ShipmentValidationIssue(BaseModel):
    """A reason a shipment is not ready to be planned."""

    field: str
    message: str


class ShipmentUploadResponse(BaseModel):
    """The result of uploading and parsing a document."""

    shipment: ShipmentDetailPublic
    issues: list[ShipmentValidationIssue] = Field(default_factory=list)
    is_duplicate: bool = False
