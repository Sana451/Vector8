"""Extracting plain text from uploaded shipping documents.

Every rate confirmation seen so far carries a real text layer, so plain text
extraction is enough and no OCR is involved. Layout is deliberately not
preserved beyond page breaks: brokers use wildly different templates, and the
downstream LLM parser reads prose better than reconstructed columns.

TODO: fall back to OCR once scanned documents without a text layer appear.
"""

from __future__ import annotations

import io

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.shipments.exceptions import DocumentTextExtractionError

PAGE_SEPARATOR = "\n\n--- page {number} ---\n\n"

MIN_USEFUL_CHARACTERS = 50


def extract_pdf_text(content: bytes) -> str:
    """Return the text of ``content`` with pages separated by markers.

    Raises ``DocumentTextExtractionError`` when the file cannot be read or
    carries too little text to be worth sending to the parser, which is the
    signal that the document is a scan and needs OCR.
    """
    try:
        reader = PdfReader(io.BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, ValueError, OSError) as exc:
        raise DocumentTextExtractionError(f"Could not read the PDF: {exc}") from exc

    parts: list[str] = []
    for number, page_text in enumerate(pages, start=1):
        stripped = page_text.strip()
        if not stripped:
            continue
        parts.append(PAGE_SEPARATOR.format(number=number))
        parts.append(stripped)

    # PostgreSQL text columns reject NUL bytes, which broken PDF fonts can emit.
    text = "".join(parts).replace("\x00", "").strip()

    if len(text.replace(" ", "").replace("\n", "")) < MIN_USEFUL_CHARACTERS:
        raise DocumentTextExtractionError(
            "The PDF has no usable text layer. It is most likely a scan, "
            "which is not supported yet."
        )

    return text
