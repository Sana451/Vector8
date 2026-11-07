"""Prompt construction for shipping document extraction.

Broker rate confirmations share no layout, so the prompt leans on describing
the target shape precisely rather than on describing the source document.
"""

from __future__ import annotations

SYSTEM_PROMPT = """\
You extract structured freight data from North American broker documents such \
as rate confirmations, load confirmations and load tenders.

Return ONLY a JSON object. No prose, no explanation, no markdown fences.

Rules:
- Use null for anything the document does not state. Never invent a value.
- Never copy a placeholder such as "N/A", "TBD" or an empty underline into a \
field; use null instead.
- "stops" lists every pickup and delivery in the order they are served, \
starting at sequence 1. Most documents have one pickup and one delivery, but \
multi-stop loads exist and every stop must be listed.
- "kind" is "pickup" when freight is loaded and "dropoff" when it is unloaded.
- "address" must be the complete street address with city, state and ZIP, \
joined into one line. Do not include the company name in it.
- Dates and times must be ISO 8601 local time, for example \
"2026-11-03T08:00:00". If a document gives only a date, use midnight. If it \
gives a window, put its start in "scheduled_at_start" and its end in \
"scheduled_at_end". A two-digit year like 11/03/26 means 2026.
- "reference_number" at the top level is the broker's load or PRO number for \
the whole order. A pickup number or delivery number belongs to its stop.
- "rate_total" is the total the carrier is paid, as a plain number without a \
currency symbol or thousands separators. Brokers label it differently, for \
example "Rate", "Total", "Line haul" or "Amount to invoice"; use the main \
load amount, not per-day or per-hour fees such as layover or detention.
- "total_weight_lbs" is the weight of the whole load in pounds. Convert from \
kilograms if needed.
- "notes" holds carrier instructions that matter operationally. Skip boilerplate \
legal terms, payment portal instructions and signature blocks.
- "extras" is a flat string-to-string map for anything else worth keeping, for \
example "mc_number" or "commodity".
- "field_confidence" maps each top-level field name you filled to your \
confidence from 0 to 1. Be honest: use a low value when the document is \
ambiguous or the layout made you guess. A dispatcher reviews low-confidence \
fields by hand, so understating confidence is cheap and overstating it is not.
- "overall_confidence" is your confidence in the extraction as a whole.

The JSON object must have exactly these keys:

{
  "broker_name": string|null,
  "broker_contact": string|null,
  "reference_number": string|null,
  "total_weight_lbs": number|null,
  "rate_total": number|null,
  "rate_currency": string|null,
  "equipment_type": string|null,
  "notes": string|null,
  "stops": [
    {
      "sequence": number,
      "kind": "pickup"|"dropoff",
      "company_name": string|null,
      "address": string,
      "scheduled_at_start": string|null,
      "scheduled_at_end": string|null,
      "reference_number": string|null,
      "contact_name": string|null,
      "contact_phone": string|null,
      "notes": string|null
    }
  ],
  "extras": {"key": "value"},
  "field_confidence": {"field_name": number},
  "overall_confidence": number
}\
"""

USER_PROMPT = """\
Extract the freight data from this document.

<document>
{text}
</document>\
"""

REPAIR_PROMPT = """\
Your previous answer could not be used:

{error}

Return the corrected JSON object only. No prose, no markdown fences.\
"""

MAX_DOCUMENT_CHARACTERS = 60_000


def build_messages(text: str) -> list[dict[str, str]]:
    """Return the chat messages extracting ``text``.

    Long documents are truncated from the end: rate confirmations put the load
    details on the first pages and legal boilerplate on the last ones, so the
    tail is the safe part to lose.
    """
    truncated = text[:MAX_DOCUMENT_CHARACTERS]
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT.format(text=truncated)},
    ]


def build_repair_messages(
    text: str,
    *,
    previous_answer: str,
    error: str,
) -> list[dict[str, str]]:
    """Return messages asking the model to fix its own invalid answer."""
    return [
        *build_messages(text),
        {"role": "assistant", "content": previous_answer},
        {"role": "user", "content": REPAIR_PROMPT.format(error=error)},
    ]
