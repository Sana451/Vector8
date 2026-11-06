"""The shipment intake endpoints, end to end against fake providers."""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.providers.exceptions import ProviderError
from app.shipments.domain import PlanningStatus
from tests.shipments.conftest import (
    EXTRACTION_ANSWER,
    FakeGeocodingProvider,
    FakeLLMProvider,
    create_dispatcher,
    headers_for,
)

PREFIX = f"{settings.API_V1_STR}/shipments"


def upload(
    client: TestClient,
    headers: dict[str, str],
    content: bytes,
    *,
    filename: str = "rate-confirmation.pdf",
    content_type: str = "application/pdf",
) -> Any:
    return client.post(
        f"{PREFIX}/upload",
        headers=headers,
        files={"file": (filename, content, content_type)},
    )


class TestUpload:
    def test_creates_a_shipment_with_geocoded_stops(
        self,
        client: TestClient,
        db: Session,
        sample_pdf: bytes,
        fake_llm: FakeLLMProvider,
        fake_geocoder: FakeGeocodingProvider,
    ) -> None:
        user, password = create_dispatcher(db)

        response = upload(client, headers_for(client, user, password), sample_pdf)

        assert response.status_code == 201
        body = response.json()
        shipment = body["shipment"]
        assert shipment["reference_number"] == "60116404581"
        assert shipment["planning_status"] == PlanningStatus.UNPLANNED
        assert shipment["is_manually_edited"] is False
        assert len(shipment["stops"]) == 2
        assert shipment["stops"][0]["kind"] == "pickup"
        assert shipment["stops"][0]["location"]["coordinates"]
        assert shipment["documents"][0]["parse_status"] == "parsed"
        assert body["issues"] == []
        assert fake_geocoder.queries == [
            "45145 W. 12 Mile Rd, Novi, MI 48377",
            "925 East McGregor Drive, Mc Gregor, TX 76657",
        ]

    def test_sends_the_pdf_text_to_the_parser(
        self,
        client: TestClient,
        db: Session,
        sample_pdf: bytes,
        fake_llm: FakeLLMProvider,
        fake_geocoder: FakeGeocodingProvider,
    ) -> None:
        user, password = create_dispatcher(db)

        upload(client, headers_for(client, user, password), sample_pdf)

        assert "Priority 1" in fake_llm.calls[0][1]["content"]

    def test_rejects_a_file_that_is_not_a_pdf(
        self,
        client: TestClient,
        db: Session,
        fake_llm: FakeLLMProvider,
        fake_geocoder: FakeGeocodingProvider,
    ) -> None:
        user, password = create_dispatcher(db)

        response = upload(
            client,
            headers_for(client, user, password),
            b"this is a spreadsheet, honestly",
            filename="load.pdf",
        )

        assert response.status_code == 415

    def test_rejects_a_scanned_pdf_without_a_text_layer(
        self,
        client: TestClient,
        db: Session,
        fake_llm: FakeLLMProvider,
        fake_geocoder: FakeGeocodingProvider,
    ) -> None:
        user, password = create_dispatcher(db)

        response = upload(
            client, headers_for(client, user, password), b"%PDF-1.4\n%nothing here"
        )

        assert response.status_code == 422

    def test_returns_the_existing_shipment_for_a_repeated_file(
        self,
        client: TestClient,
        db: Session,
        sample_pdf: bytes,
        fake_llm: FakeLLMProvider,
        fake_geocoder: FakeGeocodingProvider,
    ) -> None:
        user, password = create_dispatcher(db)
        headers = headers_for(client, user, password)

        first = upload(client, headers, sample_pdf)
        second = upload(client, headers, sample_pdf)

        assert second.status_code == 201
        assert second.json()["is_duplicate"] is True
        assert second.json()["shipment"]["id"] == first.json()["shipment"]["id"]
        assert len(fake_llm.calls) == 1

    def test_reports_stops_that_could_not_be_geocoded(
        self,
        client: TestClient,
        db: Session,
        sample_pdf: bytes,
        fake_llm: FakeLLMProvider,
        fake_geocoder: FakeGeocodingProvider,
    ) -> None:
        user, password = create_dispatcher(db)
        fake_geocoder.error = ProviderError("address not found")

        response = upload(client, headers_for(client, user, password), sample_pdf)

        body = response.json()
        assert response.status_code == 201
        assert body["shipment"]["stops"][0]["location"] is None
        assert "address not found" in body["shipment"]["stops"][0]["geocode_error"]
        assert len(body["issues"]) == 2

    def test_requires_authentication(
        self, client: TestClient, sample_pdf: bytes
    ) -> None:
        response = upload(client, {}, sample_pdf)

        assert response.status_code == 401


class TestRead:
    def test_lists_only_the_callers_shipments(
        self,
        client: TestClient,
        db: Session,
        sample_pdf: bytes,
        fake_llm: FakeLLMProvider,
        fake_geocoder: FakeGeocodingProvider,
    ) -> None:
        owner, owner_password = create_dispatcher(db)
        other, other_password = create_dispatcher(db)
        upload(client, headers_for(client, owner, owner_password), sample_pdf)

        response = client.get(
            f"{PREFIX}/", headers=headers_for(client, other, other_password)
        )

        assert response.status_code == 200
        assert response.json()["count"] == 0

    def test_filters_by_planning_status(
        self,
        client: TestClient,
        db: Session,
        sample_pdf: bytes,
        fake_llm: FakeLLMProvider,
        fake_geocoder: FakeGeocodingProvider,
    ) -> None:
        user, password = create_dispatcher(db)
        headers = headers_for(client, user, password)
        upload(client, headers, sample_pdf)

        unplanned = client.get(
            f"{PREFIX}/", headers=headers, params={"planning_status": "unplanned"}
        )
        planned = client.get(
            f"{PREFIX}/", headers=headers, params={"planning_status": "planned"}
        )

        assert unplanned.json()["count"] == 1
        assert planned.json()["count"] == 0

    def test_hides_another_users_shipment(
        self,
        client: TestClient,
        db: Session,
        sample_pdf: bytes,
        fake_llm: FakeLLMProvider,
        fake_geocoder: FakeGeocodingProvider,
    ) -> None:
        owner, owner_password = create_dispatcher(db)
        other, other_password = create_dispatcher(db)
        created = upload(
            client, headers_for(client, owner, owner_password), sample_pdf
        ).json()["shipment"]

        response = client.get(
            f"{PREFIX}/{created['id']}",
            headers=headers_for(client, other, other_password),
        )

        assert response.status_code == 403

    def test_serves_the_original_file(
        self,
        client: TestClient,
        db: Session,
        sample_pdf: bytes,
        fake_llm: FakeLLMProvider,
        fake_geocoder: FakeGeocodingProvider,
    ) -> None:
        user, password = create_dispatcher(db)
        headers = headers_for(client, user, password)
        created = upload(client, headers, sample_pdf).json()["shipment"]
        document_id = created["documents"][0]["id"]

        response = client.get(f"{PREFIX}/documents/{document_id}/file", headers=headers)

        assert response.status_code == 200
        assert response.content == sample_pdf
        assert response.headers["content-type"] == "application/pdf"


class TestUpdate:
    def test_applies_corrections_and_marks_the_shipment_edited(
        self,
        client: TestClient,
        db: Session,
        sample_pdf: bytes,
        fake_llm: FakeLLMProvider,
        fake_geocoder: FakeGeocodingProvider,
    ) -> None:
        user, password = create_dispatcher(db)
        headers = headers_for(client, user, password)
        created = upload(client, headers, sample_pdf).json()["shipment"]

        response = client.patch(
            f"{PREFIX}/{created['id']}",
            headers=headers,
            json={"broker_name": "Corrected Broker", "rate_total": "3100.00"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["broker_name"] == "Corrected Broker"
        assert body["is_manually_edited"] is True
        assert len(body["stops"]) == 2

    def test_replacing_stops_renumbers_and_regeocodes_them(
        self,
        client: TestClient,
        db: Session,
        sample_pdf: bytes,
        fake_llm: FakeLLMProvider,
        fake_geocoder: FakeGeocodingProvider,
    ) -> None:
        user, password = create_dispatcher(db)
        headers = headers_for(client, user, password)
        created = upload(client, headers, sample_pdf).json()["shipment"]

        response = client.patch(
            f"{PREFIX}/{created['id']}",
            headers=headers,
            json={
                "stops": [
                    {"kind": "pickup", "address_raw": "1 First St, Detroit, MI"},
                    {"kind": "dropoff", "address_raw": "2 Second St, Dallas, TX"},
                    {"kind": "dropoff", "address_raw": "3 Third St, Austin, TX"},
                ]
            },
        )

        assert response.status_code == 200
        stops = response.json()["stops"]
        assert [stop["sequence"] for stop in stops] == [1, 2, 3]
        assert fake_geocoder.queries[-1] == "3 Third St, Austin, TX"

    def test_rejects_an_empty_stop_address(
        self,
        client: TestClient,
        db: Session,
        sample_pdf: bytes,
        fake_llm: FakeLLMProvider,
        fake_geocoder: FakeGeocodingProvider,
    ) -> None:
        user, password = create_dispatcher(db)
        headers = headers_for(client, user, password)
        created = upload(client, headers, sample_pdf).json()["shipment"]

        response = client.patch(
            f"{PREFIX}/{created['id']}",
            headers=headers,
            json={"stops": [{"kind": "pickup", "address_raw": "   "}]},
        )

        assert response.status_code == 422


class TestReparse:
    def test_discards_manual_edits(
        self,
        client: TestClient,
        db: Session,
        sample_pdf: bytes,
        fake_llm: FakeLLMProvider,
        fake_geocoder: FakeGeocodingProvider,
    ) -> None:
        user, password = create_dispatcher(db)
        headers = headers_for(client, user, password)
        created = upload(client, headers, sample_pdf).json()["shipment"]
        client.patch(
            f"{PREFIX}/{created['id']}",
            headers=headers,
            json={"broker_name": "Typed by hand"},
        )

        corrected = dict(EXTRACTION_ANSWER)
        corrected["broker_name"] = "Re-parsed Broker"
        fake_llm.answers = [json.dumps(corrected)]

        response = client.post(f"{PREFIX}/{created['id']}/reparse", headers=headers)

        assert response.status_code == 200
        body = response.json()
        assert body["broker_name"] == "Re-parsed Broker"
        assert body["is_manually_edited"] is False
        assert len(body["stops"]) == 2


class TestDelete:
    def test_removes_the_shipment(
        self,
        client: TestClient,
        db: Session,
        sample_pdf: bytes,
        fake_llm: FakeLLMProvider,
        fake_geocoder: FakeGeocodingProvider,
    ) -> None:
        user, password = create_dispatcher(db)
        headers = headers_for(client, user, password)
        created = upload(client, headers, sample_pdf).json()["shipment"]

        deleted = client.delete(f"{PREFIX}/{created['id']}", headers=headers)
        fetched = client.get(f"{PREFIX}/{created['id']}", headers=headers)

        assert deleted.status_code == 204
        assert fetched.status_code == 404
