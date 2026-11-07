"""Persistence models for shipments and their source documents.

Three tables cover the intake flow:

``shipments``
    The freight order itself. Only fields the application actually uses get
    their own column; everything else the parser reads stays in
    ``extracted_payload``, mirroring how ``FuelStation.payload`` is handled.

``shipment_stops``
    Ordered pickup and dropoff stops. These become routing waypoints when a
    trip is planned, which may be long after the document was uploaded.

``shipment_documents``
    The uploaded PDF plus everything needed to re-run or audit extraction.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Column, Field, SQLModel

from app.core.datetime import get_datetime_utc
from app.shipments.domain import DocumentParseStatus, PlanningStatus, StopKind


class Shipment(SQLModel, table=True):
    """A freight order extracted from a broker rate confirmation."""

    __tablename__ = "shipments"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    planning_status: PlanningStatus = Field(
        default=PlanningStatus.UNPLANNED,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    broker_name: str | None = Field(
        default=None, sa_column=Column(String(length=255), nullable=True, index=True)
    )
    broker_contact: str | None = Field(
        default=None, sa_column=Column(String(length=512), nullable=True)
    )
    reference_number: str | None = Field(
        default=None, sa_column=Column(String(length=128), nullable=True, index=True)
    )
    total_weight_lbs: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(12, 2), nullable=True)
    )
    rate_total: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(12, 2), nullable=True)
    )
    rate_currency: str | None = Field(
        default=None, sa_column=Column(String(length=8), nullable=True)
    )
    equipment_type: str | None = Field(
        default=None, sa_column=Column(String(length=128), nullable=True)
    )
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    extracted_payload: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    extraction_confidence: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(4, 3), nullable=True)
    )
    field_confidence: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    is_manually_edited: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ShipmentStop(SQLModel, table=True):
    """One pickup or dropoff on a shipment, ordered by ``sequence``.

    ``location`` stays nullable because geocoding an address from a scanned
    document can fail; such a shipment is still worth keeping and editing by
    hand, it just cannot be planned until every stop resolves to a point.
    """

    __tablename__ = "shipment_stops"
    __table_args__ = (
        UniqueConstraint("shipment_id", "sequence", name="uq_shipment_stop_sequence"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    shipment_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    sequence: int = Field(sa_column=Column(Integer, nullable=False))
    kind: StopKind = Field(sa_column=Column(String(length=16), nullable=False))
    company_name: str | None = Field(
        default=None, sa_column=Column(String(length=255), nullable=True)
    )
    address_raw: str = Field(sa_column=Column(String(length=512), nullable=False))
    location: str | None = Field(
        default=None,
        sa_column=Column(
            Geography(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
    )
    geocoded_address: str | None = Field(
        default=None, sa_column=Column(String(length=512), nullable=True)
    )
    geocode_error: str | None = Field(
        default=None, sa_column=Column(String(length=512), nullable=True)
    )
    scheduled_at_start: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    scheduled_at_end: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    reference_number: str | None = Field(
        default=None, sa_column=Column(String(length=128), nullable=True)
    )
    contact_name: str | None = Field(
        default=None, sa_column=Column(String(length=255), nullable=True)
    )
    contact_phone: str | None = Field(
        default=None, sa_column=Column(String(length=64), nullable=True)
    )
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ShipmentDocument(SQLModel, table=True):
    """An uploaded source document and the raw material behind its parse.

    ``extracted_text`` and ``raw_llm_response`` are kept so a re-parse never
    needs the PDF reader again and so manual edits can always be diffed
    against what the model originally returned.

    TODO: ``content`` holds the file bytes inline. Move to S3 or a mounted
    volume and keep only a storage key here once object storage exists.
    """

    __tablename__ = "shipment_documents"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    shipment_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("shipments.id", ondelete="CASCADE"), nullable=True, index=True
        ),
    )
    uploaded_by_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )
    filename: str = Field(sa_column=Column(String(length=255), nullable=False))
    content_type: str = Field(sa_column=Column(String(length=128), nullable=False))
    size_bytes: int = Field(sa_column=Column(Integer, nullable=False))
    content: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    content_sha256: str = Field(
        sa_column=Column(String(length=64), nullable=False, index=True)
    )
    extracted_text: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    raw_llm_response: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    parse_status: DocumentParseStatus = Field(
        default=DocumentParseStatus.PENDING,
        sa_column=Column(String(length=32), nullable=False, index=True),
    )
    parse_error: str | None = Field(
        default=None, sa_column=Column(String(length=1024), nullable=True)
    )
    parsed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    uploaded_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
