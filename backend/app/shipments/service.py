"""Application service for the shipment intake flow."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import structlog
from sqlmodel import Session

from app.core.datetime import get_datetime_utc
from app.geocoding.service import GeocodingService
from app.models import User, UserRole
from app.providers.geo import GeoJSONPoint, point_to_wkt
from app.shipments.domain import DocumentParseStatus, PlanningStatus, StopKind
from app.shipments.exceptions import (
    DocumentTooLargeError,
    ShipmentAccessDeniedError,
    ShipmentDocumentNotFoundError,
    ShipmentNotFoundError,
    UnsupportedDocumentTypeError,
)
from app.shipments.extraction.parser import ShipmentDocumentParser
from app.shipments.extraction.pdf import extract_pdf_text
from app.shipments.extraction.schemas import ExtractedStop, ShipmentExtraction
from app.shipments.geocoding import geocode_stops
from app.shipments.models import Shipment, ShipmentDocument, ShipmentStop
from app.shipments.repository import ShipmentRepository
from app.shipments.schemas import (
    ShipmentDetailPublic,
    ShipmentDocumentPublic,
    ShipmentPublic,
    ShipmentStopPublic,
    ShipmentStopWrite,
    ShipmentUpdateRequest,
    ShipmentValidationIssue,
)

logger = structlog.get_logger(__name__)

MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
PDF_MAGIC = b"%PDF-"
ALLOWED_CONTENT_TYPES = frozenset({"application/pdf", "application/x-pdf"})


class ShipmentService:
    """Uploads, parses, corrects and serves shipments.

    Parsing runs inline with the upload request. That is acceptable while a
    document takes a few seconds, and it keeps the client flow simple: the
    dispatcher sees the extracted fields immediately.

    TODO: move parsing to a Celery task once a dedicated server with a worker
    is available, returning the shipment in a ``pending`` state instead.
    """

    def __init__(
        self,
        *,
        session: Session,
        parser: ShipmentDocumentParser,
        geocoding_service: GeocodingService,
    ) -> None:
        self.repository = ShipmentRepository(session)
        self.parser = parser
        self.geocoding_service = geocoding_service

    async def upload_document(
        self,
        *,
        content: bytes,
        filename: str,
        content_type: str | None,
        owner_id: uuid.UUID,
    ) -> tuple[Shipment, bool]:
        """Store a document, parse it and return the resulting shipment.

        The boolean reports whether an identical file had already been
        uploaded, in which case the existing shipment is returned untouched.
        """
        _validate_upload(content=content, content_type=content_type)
        content_sha256 = hashlib.sha256(content).hexdigest()

        existing = self.repository.find_shipment_by_content_hash(
            owner_id, content_sha256
        )
        if existing is not None:
            logger.info(
                "Duplicate shipment document ignored",
                shipment_id=str(existing.id),
                content_sha256=content_sha256,
            )
            return existing, True

        text = extract_pdf_text(content)

        document = ShipmentDocument(
            uploaded_by_id=owner_id,
            filename=filename,
            content_type=content_type or "application/pdf",
            size_bytes=len(content),
            content=content,
            content_sha256=content_sha256,
            extracted_text=text,
        )

        try:
            extraction, raw_answer = await self.parser.parse(text)
        except Exception as exc:
            document.parse_status = DocumentParseStatus.FAILED
            document.parse_error = str(exc)[:1024]
            self.repository.add(document)
            self.repository.commit()
            raise

        document.raw_llm_response = raw_answer
        document.parse_status = DocumentParseStatus.PARSED
        document.parsed_at = get_datetime_utc()

        shipment = _shipment_from_extraction(extraction, owner_id=owner_id)
        self.repository.add(shipment)
        document.shipment_id = shipment.id
        self.repository.add(document)

        await self._persist_stops(shipment.id, extraction.stops)
        self.repository.commit()
        self.repository.refresh(shipment)
        return shipment, False

    async def reparse(self, shipment_id: uuid.UUID, *, owner_id: uuid.UUID) -> Shipment:
        """Re-run extraction on the shipment's most recent document.

        Manual corrections are overwritten, which is the point: a re-parse is
        asked for when the first attempt was wrong, not when it was edited.
        """
        shipment = self._get_owned(shipment_id, owner_id=owner_id)
        documents = self.repository.list_documents(shipment_id)
        if not documents:
            raise ShipmentDocumentNotFoundError(
                "This shipment has no document to re-parse."
            )

        document = documents[0]
        text = document.extracted_text or extract_pdf_text(document.content)
        extraction, raw_answer = await self.parser.parse(text)

        document.extracted_text = text
        document.raw_llm_response = raw_answer
        document.parse_status = DocumentParseStatus.PARSED
        document.parse_error = None
        document.parsed_at = get_datetime_utc()
        self.repository.add(document)

        _apply_extraction(shipment, extraction)
        shipment.is_manually_edited = False
        shipment.updated_at = get_datetime_utc()
        self.repository.add(shipment)

        self.repository.delete_stops(shipment_id)
        await self._persist_stops(shipment_id, extraction.stops)
        self.repository.commit()
        self.repository.refresh(shipment)
        return shipment

    async def update(
        self,
        shipment_id: uuid.UUID,
        request: ShipmentUpdateRequest,
        *,
        owner_id: uuid.UUID,
    ) -> Shipment:
        """Apply a dispatcher's corrections."""
        shipment = self._get_owned(shipment_id, owner_id=owner_id)
        fields = request.model_dump(exclude_unset=True, exclude={"stops"})
        for name, value in fields.items():
            setattr(shipment, name, value)

        if request.stops is not None:
            self.repository.delete_stops(shipment_id)
            await self._persist_stops(
                shipment_id,
                [
                    _stop_write_to_extracted(stop, index)
                    for index, stop in enumerate(request.stops, start=1)
                ],
            )

        shipment.is_manually_edited = True
        shipment.updated_at = get_datetime_utc()
        self.repository.add(shipment)
        self.repository.commit()
        self.repository.refresh(shipment)
        return shipment

    def delete(self, shipment_id: uuid.UUID, *, user: User) -> None:
        """Admins may delete any shipment; dispatchers only their own."""
        shipment = self.repository.get(shipment_id)
        if shipment is None:
            raise ShipmentNotFoundError("This shipment does not exist.")
        if not (
            user.role == UserRole.ADMIN
            or user.is_superuser
            or shipment.owner_id == user.id
        ):
            raise ShipmentAccessDeniedError("This shipment belongs to another user.")
        self.repository.delete(shipment)
        self.repository.commit()

    def list_shipments(
        self,
        *,
        owner_id: uuid.UUID,
        planning_status: PlanningStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[ShipmentPublic], int]:
        shipments, total = self.repository.list_for_owner(
            owner_id, planning_status=planning_status, skip=skip, limit=limit
        )
        return [ShipmentPublic.model_validate(item) for item in shipments], total

    def get_detail(
        self, shipment_id: uuid.UUID, *, owner_id: uuid.UUID
    ) -> ShipmentDetailPublic:
        shipment = self._get_owned(shipment_id, owner_id=owner_id)
        return self.build_detail(shipment)

    def build_detail(self, shipment: Shipment) -> ShipmentDetailPublic:
        detail = ShipmentDetailPublic.model_validate(shipment)
        detail.stops = [
            _stop_to_public(stop, point)
            for stop, point in self.repository.list_stops_with_points(shipment.id)
        ]
        detail.documents = [
            ShipmentDocumentPublic.model_validate(document)
            for document in self.repository.list_documents(shipment.id)
        ]
        return detail

    def get_document(
        self, document_id: uuid.UUID, *, owner_id: uuid.UUID
    ) -> ShipmentDocument:
        document = self.repository.get_document(document_id)
        if document is None:
            raise ShipmentDocumentNotFoundError("This document does not exist.")
        if document.shipment_id is not None:
            self._get_owned(document.shipment_id, owner_id=owner_id)
        elif document.uploaded_by_id != owner_id:
            raise ShipmentAccessDeniedError("This document belongs to another user.")
        return document

    def validate_for_planning(
        self, shipment_id: uuid.UUID, *, owner_id: uuid.UUID
    ) -> list[ShipmentValidationIssue]:
        """Report why a shipment cannot be planned yet.

        These are returned as warnings rather than raised, so the review screen
        can show a dispatcher exactly what to fix.
        """
        self._get_owned(shipment_id, owner_id=owner_id)
        stops = self.repository.list_stops(shipment_id)
        issues: list[ShipmentValidationIssue] = []

        if len(stops) < 2:
            issues.append(
                ShipmentValidationIssue(
                    field="stops",
                    message="A shipment needs at least a pickup and a dropoff.",
                )
            )
        if not any(stop.kind == StopKind.PICKUP for stop in stops):
            issues.append(
                ShipmentValidationIssue(
                    field="stops", message="No pickup stop was recognised."
                )
            )
        if not any(stop.kind == StopKind.DROPOFF for stop in stops):
            issues.append(
                ShipmentValidationIssue(
                    field="stops", message="No delivery stop was recognised."
                )
            )
        for stop in stops:
            if stop.location is None:
                issues.append(
                    ShipmentValidationIssue(
                        field=f"stops.{stop.sequence}.address_raw",
                        message=(
                            f"Stop {stop.sequence} has no coordinates: "
                            f"{stop.geocode_error or 'the address could not be resolved'}"
                        ),
                    )
                )
        return issues

    async def _persist_stops(
        self, shipment_id: uuid.UUID, stops: list[ExtractedStop]
    ) -> None:
        ordered: list[ExtractedStop] = sorted(stops, key=lambda stop: stop.sequence)
        geocoded = await geocode_stops(ordered, service=self.geocoding_service)
        for sequence, (stop, resolved) in enumerate(
            zip(ordered, geocoded, strict=True), start=1
        ):
            location = None
            if resolved.location is not None:
                longitude, latitude = resolved.location.coordinates
                location = point_to_wkt(longitude, latitude)

            self.repository.add(
                ShipmentStop(
                    shipment_id=shipment_id,
                    sequence=sequence,
                    kind=stop.kind,
                    company_name=stop.company_name,
                    address_raw=stop.address,
                    location=location,
                    geocoded_address=resolved.geocoded_address,
                    geocode_error=resolved.error,
                    scheduled_at_start=_parse_timestamp(stop.scheduled_at_start),
                    scheduled_at_end=_parse_timestamp(stop.scheduled_at_end),
                    reference_number=stop.reference_number,
                    contact_name=stop.contact_name,
                    contact_phone=stop.contact_phone,
                    notes=stop.notes,
                )
            )

    def _get_owned(self, shipment_id: uuid.UUID, *, owner_id: uuid.UUID) -> Shipment:
        shipment = self.repository.get(shipment_id)
        if shipment is None:
            raise ShipmentNotFoundError("This shipment does not exist.")
        if shipment.owner_id != owner_id:
            raise ShipmentAccessDeniedError("This shipment belongs to another user.")
        return shipment


def _validate_upload(*, content: bytes, content_type: str | None) -> None:
    if len(content) > MAX_DOCUMENT_BYTES:
        raise DocumentTooLargeError(
            f"The document exceeds the {MAX_DOCUMENT_BYTES // (1024 * 1024)} MB limit."
        )
    if content_type is not None and content_type.split(";")[0].strip().lower() not in (
        ALLOWED_CONTENT_TYPES
    ):
        raise UnsupportedDocumentTypeError("Only PDF documents can be uploaded.")
    if not content.startswith(PDF_MAGIC):
        raise UnsupportedDocumentTypeError(
            "The uploaded file is not a PDF, whatever its name says."
        )


def _shipment_from_extraction(
    extraction: ShipmentExtraction, *, owner_id: uuid.UUID
) -> Shipment:
    shipment = Shipment(owner_id=owner_id, planning_status=PlanningStatus.UNPLANNED)
    _apply_extraction(shipment, extraction)
    return shipment


def _apply_extraction(shipment: Shipment, extraction: ShipmentExtraction) -> None:
    shipment.broker_name = extraction.broker_name
    shipment.broker_contact = extraction.broker_contact
    shipment.reference_number = extraction.reference_number
    shipment.total_weight_lbs = extraction.total_weight_lbs
    shipment.rate_total = extraction.rate_total
    shipment.rate_currency = extraction.rate_currency
    shipment.equipment_type = extraction.equipment_type
    shipment.notes = extraction.notes
    shipment.extracted_payload = extraction.model_dump(mode="json")
    shipment.field_confidence = dict(extraction.field_confidence)
    shipment.extraction_confidence = Decimal(str(extraction.overall_confidence))


def _stop_write_to_extracted(stop: ShipmentStopWrite, sequence: int) -> ExtractedStop:
    return ExtractedStop(
        sequence=sequence,
        kind=stop.kind,
        company_name=stop.company_name,
        address=stop.address_raw,
        scheduled_at_start=stop.scheduled_at_start.isoformat()
        if stop.scheduled_at_start
        else None,
        scheduled_at_end=stop.scheduled_at_end.isoformat()
        if stop.scheduled_at_end
        else None,
        reference_number=stop.reference_number,
        contact_name=stop.contact_name,
        contact_phone=stop.contact_phone,
        notes=stop.notes,
    )


def _stop_to_public(
    stop: ShipmentStop, location: GeoJSONPoint | None
) -> ShipmentStopPublic:
    """Build the public stop, taking coordinates from a PostGIS read.

    ``location`` is excluded because SQLAlchemy hands back a ``WKBElement``,
    which Pydantic cannot interpret. Serializer warnings are silenced because
    the string columns backing the enums dump as plain strings, which the
    public model then validates back into enum members.
    """
    payload = stop.model_dump(exclude={"location"}, warnings=False)
    payload["location"] = location
    return ShipmentStopPublic.model_validate(payload)


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse an ISO 8601 timestamp, assuming UTC when no offset is given.

    Broker documents state local times without a zone, and the stop's own
    timezone is not known until its address is resolved to a region. Treating
    naive values as UTC keeps them comparable and ordered; a later change can
    refine them once stop timezones are available.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        logger.info("Unparsable schedule timestamp discarded", value=value[:64])
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
