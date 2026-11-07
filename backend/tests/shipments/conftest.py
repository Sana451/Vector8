"""Shared fixtures and fakes for the shipments tests."""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.geocoding.dependencies import get_geocoding_provider
from app.geocoding.repository import GeocodingCacheEntry
from app.geocoding.schemas import GeocodingResult
from app.llm.base import LLMProviderError
from app.main import app
from app.models import User, UserRole
from app.providers.exceptions import ProviderError
from app.providers.geo import GeoJSONPoint
from app.shipments.dependencies import get_document_parser
from app.shipments.extraction.parser import ShipmentDocumentParser

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "invoices_examples"

EXTRACTION_ANSWER: dict[str, object] = {
    "broker_name": "Priority 1 Inc.",
    "broker_contact": "tlap@priority1.com",
    "reference_number": "60116404581",
    "total_weight_lbs": 5600,
    "rate_total": 2900,
    "rate_currency": "USD",
    "equipment_type": "Large Straight",
    "notes": "Call when loaded and empty.",
    "stops": [
        {
            "sequence": 1,
            "kind": "pickup",
            "company_name": "Our Next Energy",
            "address": "45145 W. 12 Mile Rd, Novi, MI 48377",
            "scheduled_at_start": "2026-10-30T08:00:00",
            "scheduled_at_end": None,
            "reference_number": None,
            "contact_name": "Jeanne Whitney",
            "contact_phone": "+17343866946",
            "notes": None,
        },
        {
            "sequence": 2,
            "kind": "dropoff",
            "company_name": "Wheelhorse Industries, LLC",
            "address": "925 East McGregor Drive, Mc Gregor, TX 76657",
            "scheduled_at_start": "2026-11-02T08:00:00",
            "scheduled_at_end": "2026-11-02T16:00:00",
            "reference_number": None,
            "contact_name": "Jason Hollingsworth",
            "contact_phone": "+19039488420",
            "notes": None,
        },
    ],
    "extras": {"commodity": "Lithium-Ion Batteries"},
    "field_confidence": {"broker_name": 0.95, "rate_total": 0.9},
    "overall_confidence": 0.9,
}


class FakeLLMProvider:
    """An LLM stand-in that replays scripted answers."""

    def __init__(self, answers: list[str] | None = None) -> None:
        self.answers = answers or [json.dumps(EXTRACTION_ANSWER)]
        self.calls: list[list[dict[str, str]]] = []
        self.error: Exception | None = None

    def get_name(self) -> str:
        return "fake"

    async def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        if self.error is not None:
            raise self.error
        index = min(len(self.calls) - 1, len(self.answers) - 1)
        return self.answers[index]


class FakeGeocodingProvider:
    """Returns a fixed point per query, or fails when asked to."""

    def __init__(self) -> None:
        self.queries: list[str] = []
        self.error: Exception | None = None

    async def search(self, query: str) -> GeocodingResult:
        self.queries.append(query)
        if self.error is not None:
            raise self.error
        offset = len(self.queries) * 0.01
        return GeocodingResult(
            formatted_address=f"Resolved: {query}",
            location=GeoJSONPoint(coordinates=(-83.47 + offset, 42.48 + offset)),
            provider_id=f"id-{len(self.queries)}",
        )


@pytest.fixture
def fake_llm() -> Generator[FakeLLMProvider]:
    fake = FakeLLMProvider()
    app.dependency_overrides[get_document_parser] = lambda: ShipmentDocumentParser(fake)  # type: ignore[arg-type]
    yield fake
    app.dependency_overrides.pop(get_document_parser, None)


@pytest.fixture
def fake_geocoder(db: Session) -> Generator[FakeGeocodingProvider]:
    # The geocoding cache is a database table that outlives a test run, so it
    # would otherwise answer from a previous run's fake and the provider would
    # never be called.
    db.execute(delete(GeocodingCacheEntry))
    db.commit()
    fake = FakeGeocodingProvider()
    app.dependency_overrides[get_geocoding_provider] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_geocoding_provider, None)


@pytest.fixture
def sample_pdf() -> bytes:
    """A real rate confirmation, so PDF text extraction is exercised too."""
    path = SAMPLES_DIR / "Invoice #5561 Pro #60116404581.pdf"
    if not path.exists():
        pytest.skip("Sample rate confirmations are not available in this checkout.")
    return path.read_bytes()


def create_dispatcher(db: Session) -> tuple[User, str]:
    """Create a dispatcher able to call the shipment endpoints."""
    from tests.trip_plans.factories import create_user_with_role

    return create_user_with_role(db, UserRole.DISPATCHER)


def headers_for(client: TestClient, user: User, secret: str) -> dict[str, str]:
    """Return authentication headers for ``user``."""
    from tests.trip_plans.factories import headers_for as _headers_for

    return _headers_for(client, user, secret)


__all__ = [
    "EXTRACTION_ANSWER",
    "FakeGeocodingProvider",
    "FakeLLMProvider",
    "LLMProviderError",
    "ProviderError",
    "create_dispatcher",
    "headers_for",
]
