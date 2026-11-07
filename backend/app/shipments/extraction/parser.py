"""Turning document text into a validated ``ShipmentExtraction``.

The language model is asked for JSON and is given one chance to repair its own
answer, because the common failure is a near-miss: a stray markdown fence, a
trailing comment or one field of the wrong type.
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog
from pydantic import ValidationError

from app.llm.base import LLMProvider, LLMProviderError
from app.shipments.exceptions import DocumentParsingError
from app.shipments.extraction.prompt import build_messages, build_repair_messages
from app.shipments.extraction.schemas import ShipmentExtraction

logger = structlog.get_logger(__name__)

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _strip_fences(answer: str) -> str:
    return _FENCE_RE.sub("", answer).strip()


def _isolate_object(answer: str) -> str:
    """Return the outermost JSON object in ``answer``.

    Some models prepend a sentence despite being told not to. Cutting to the
    first ``{`` and the last ``}`` recovers those answers without a round trip.
    """
    start = answer.find("{")
    end = answer.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return answer
    return answer[start : end + 1]


def _decode(answer: str) -> dict[str, Any]:
    cleaned = _isolate_object(_strip_fences(answer))
    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise ValueError("The top-level JSON value must be an object")
    return payload


class ShipmentDocumentParser:
    """Extracts shipment fields from document text using an LLM."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def parse(self, text: str) -> tuple[ShipmentExtraction, str]:
        """Return the extraction and the raw model answer behind it.

        The raw answer is kept by the caller so manual edits can later be
        diffed against what the model originally produced.
        """
        try:
            answer = await self._llm.complete(build_messages(text))
        except LLMProviderError as exc:
            raise DocumentParsingError(f"The parser is unavailable: {exc}") from exc

        try:
            return ShipmentExtraction.model_validate(_decode(answer)), answer
        except (ValidationError, ValueError) as exc:
            logger.info(
                "Shipment extraction needs repair",
                provider=self._llm.get_name(),
                error=str(exc)[:500],
            )
            return await self._repair(text, previous_answer=answer, error=str(exc))

    async def _repair(
        self,
        text: str,
        *,
        previous_answer: str,
        error: str,
    ) -> tuple[ShipmentExtraction, str]:
        try:
            answer = await self._llm.complete(
                build_repair_messages(
                    text,
                    previous_answer=previous_answer,
                    error=error[:1000],
                )
            )
        except LLMProviderError as exc:
            raise DocumentParsingError(f"The parser is unavailable: {exc}") from exc

        try:
            return ShipmentExtraction.model_validate(_decode(answer)), answer
        except (ValidationError, ValueError) as exc:
            raise DocumentParsingError(
                f"The parser returned data that could not be validated: {exc}"
            ) from exc
