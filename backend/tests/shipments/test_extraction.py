"""Parsing a broker document into a validated extraction."""

from __future__ import annotations

import json

import pytest

from app.llm.base import LLMProviderError
from app.shipments.domain import StopKind
from app.shipments.exceptions import DocumentParsingError, DocumentTextExtractionError
from app.shipments.extraction.parser import ShipmentDocumentParser
from app.shipments.extraction.pdf import extract_pdf_text
from app.shipments.extraction.prompt import MAX_DOCUMENT_CHARACTERS, build_messages
from tests.shipments.conftest import EXTRACTION_ANSWER, FakeLLMProvider


class TestPdfExtraction:
    def test_reads_text_from_a_real_rate_confirmation(self, sample_pdf: bytes) -> None:
        text = extract_pdf_text(sample_pdf)

        assert "Priority 1" in text
        assert "Novi, MI" in text

    def test_rejects_a_document_without_a_text_layer(self) -> None:
        with pytest.raises(DocumentTextExtractionError):
            extract_pdf_text(b"%PDF-1.4\n%garbage")


class TestPrompt:
    def test_truncates_overlong_documents(self) -> None:
        messages = build_messages("x" * (MAX_DOCUMENT_CHARACTERS + 5_000))

        assert len(messages[1]["content"]) < MAX_DOCUMENT_CHARACTERS + 2_000


class TestParser:
    async def test_parses_a_plain_json_answer(self) -> None:
        parser = ShipmentDocumentParser(FakeLLMProvider())  # type: ignore[arg-type]

        extraction, raw = await parser.parse("document text")

        assert extraction.reference_number == "60116404581"
        assert [stop.kind for stop in extraction.stops] == [
            StopKind.PICKUP,
            StopKind.DROPOFF,
        ]
        assert raw.strip().startswith("{")

    async def test_recovers_an_answer_wrapped_in_markdown(self) -> None:
        fenced = f"```json\n{json.dumps(EXTRACTION_ANSWER)}\n```"
        parser = ShipmentDocumentParser(FakeLLMProvider([fenced]))  # type: ignore[arg-type]

        extraction, _ = await parser.parse("document text")

        assert extraction.broker_name == "Priority 1 Inc."

    async def test_recovers_an_answer_with_a_leading_sentence(self) -> None:
        chatty = f"Sure! Here you go:\n{json.dumps(EXTRACTION_ANSWER)}"
        parser = ShipmentDocumentParser(FakeLLMProvider([chatty]))  # type: ignore[arg-type]

        extraction, _ = await parser.parse("document text")

        assert extraction.broker_name == "Priority 1 Inc."

    async def test_retries_once_when_the_first_answer_is_invalid(self) -> None:
        fake = FakeLLMProvider(["not json at all", json.dumps(EXTRACTION_ANSWER)])
        parser = ShipmentDocumentParser(fake)  # type: ignore[arg-type]

        extraction, _ = await parser.parse("document text")

        assert extraction.broker_name == "Priority 1 Inc."
        assert len(fake.calls) == 2
        assert "could not be used" in fake.calls[1][-1]["content"]

    async def test_gives_up_after_the_repair_attempt(self) -> None:
        fake = FakeLLMProvider(["nope", "still nope"])
        parser = ShipmentDocumentParser(fake)  # type: ignore[arg-type]

        with pytest.raises(DocumentParsingError):
            await parser.parse("document text")

        assert len(fake.calls) == 2

    async def test_reports_an_unavailable_provider(self) -> None:
        fake = FakeLLMProvider()
        fake.error = LLMProviderError("upstream is down")
        parser = ShipmentDocumentParser(fake)  # type: ignore[arg-type]

        with pytest.raises(DocumentParsingError, match="unavailable"):
            await parser.parse("document text")
