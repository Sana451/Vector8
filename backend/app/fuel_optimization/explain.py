from __future__ import annotations

import json
import logging
from typing import Any, Literal

from app.fuel_optimization.schemas import (
    FuelOptimizationAlternativePublic,
    FuelOptimizationCalculateResponse,
    FuelOptimizationItineraryPointPublic,
)
from app.llm import LLMProvider, LLMProviderError

MAX_ALTERNATIVES_PER_STOP = 8
# Keeps the request under the provider's per-request token limit (HTTP 413).
MAX_CONTEXT_CHARS = 6000
LANGUAGE_NAMES = {"en": "English", "ru": "Russian"}
logger = logging.getLogger(__name__)

# Keep in sync with the map layer colors in
# frontend/src/components/Map/layers/Optimization*StationsLayer.tsx.
REJECTED_STATION_COLORS = {
    "duplicate_station_id": "light gray",
    "unsupported_fuel_type": "slate gray",
    "missing_diesel_price": "orange",
    "not_truck_accessible": "purple",
    "detour_distance_limit_exceeded": "red",
}
COMPARED_STATION_COLORS = {
    "not_reachable": "gray",
    "overhead_exceeds_savings": "orange",
    "nearer_cheaper_station_chosen": "blue",
    "not_cheaper_than_previous": "light gray",
    "higher_effective_price": "red",
    "tie_broken_by_distance": "blue",
    "no_fuel_to_buy": "light gray",
}

SYSTEM_PROMPT = """\
You are the assistant of a truck fuel-stop optimizer. You explain, in plain \
human language, why the optimizer built the route and stops the way it did, \
and you answer follow-up questions about it.

Rules:
- Use ONLY the facts and numbers in the OPTIMIZER CONTEXT below. Never invent \
stations, prices, distances or reasons. If the context does not contain the \
answer, say so.
- Explain the reasoning ("why"), not just the numbers. Keep it short and \
structured; avoid jargon.
- Explain terms like "effective price" (sticker price plus the cost of the \
detour and the stop) when you use them.
- Write plain text: short paragraphs and simple "-" bullets, no Markdown \
headings, tables or bold.
- Prices are USD per gallon, fuel is in gallons, distances in meters in the \
context; convert to miles/minutes for the user.
- On the map, stations the optimizer did not pick are colored by the reason \
they were skipped. Mention the color when the user asks about a station's \
color. Excluded before comparison: {rejected_colors}. Compared and not \
chosen: {compared_colors}.
- Always answer in {language_name}, regardless of the language of the \
context or of earlier messages.

OPTIMIZER CONTEXT (JSON):
{context}
"""

DEFAULT_QUESTIONS = {
    "en": {
        "route": "Explain this fuel plan in simple terms.",
        "stop": "Explain why the optimizer made this stop.",
    },
    "ru": {
        "route": "Объясни этот план заправок простыми словами.",
        "stop": "Объясни, почему оптимизатор выбрал эту остановку.",
    },
}


def _num(value: Any) -> Any:
    return None if value is None else float(value)


def _alternative_context(alt: FuelOptimizationAlternativePublic) -> dict[str, Any]:
    return {
        "name": alt.name,
        "outcome": alt.outcome,
        "map_color": COMPARED_STATION_COLORS.get(alt.outcome),
        "sticker_price": _num(alt.fuel_price_per_gallon),
        "effective_price": _num(alt.effective_price_per_gallon),
        "delta_vs_chosen_per_gallon": _num(alt.delta_vs_chosen_per_gallon),
        "detour_distance_m": _num(alt.detour_distance_meters),
        "detour_time_s": alt.detour_time_seconds,
        "cheaper_by_sticker": alt.cheaper_by_sticker,
        "estimated_savings": _num(alt.estimated_savings),
        "stop_overhead_cost": _num(alt.stop_overhead_cost),
        "total_extra_cost": _num(alt.total_extra_cost),
    }


def _point_context(
    point: FuelOptimizationItineraryPointPublic,
    max_alternatives: int = MAX_ALTERNATIVES_PER_STOP,
    brief: bool = False,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "sequence": point.sequence,
        "kind": point.kind,
        "status": point.status,
        "label": point.label,
        "route_offset_m": _num(point.route_offset_meters),
        "fuel_before_gal": _num(point.fuel_before_gallons),
        "fuel_added_gal": _num(point.fuel_added_gallons),
        "fuel_after_gal": _num(point.fuel_after_gallons),
        "price_per_gal": _num(point.fuel_price_per_gallon),
        "fuel_cost": _num(point.fuel_cost),
        "detour_distance_m": _num(point.detour_distance_meters),
        "detour_time_s": point.detour_time_seconds,
        "fuel_required_gal": _num(point.fuel_required_gallons),
        "available_fuel_gal": _num(point.available_fuel_gallons),
        "deficit_gal": _num(point.deficit_gallons),
    }
    if brief:
        data.pop("fuel_before_gal", None)
        data.pop("fuel_after_gal", None)
        data.pop("route_offset_m", None)
        data.pop("detour_time_s", None)
        if point.selection is not None:
            data["why_chosen"] = {"rule": point.selection.rule}
        return {k: v for k, v in data.items() if v is not None}
    if point.selection is not None:
        selection = point.selection
        data["why_chosen"] = {
            "rule": selection.rule,
            "sticker_price": _num(selection.sticker_price_per_gallon),
            "effective_price": _num(selection.effective_price_per_gallon),
            "detour_fuel_cost": _num(selection.detour_fuel_cost),
            "time_cost": _num(selection.time_cost),
            "fixed_stop_cost": _num(selection.fixed_stop_cost),
            "estimated_savings": _num(selection.estimated_savings),
            "stop_overhead_cost": _num(selection.stop_overhead_cost),
            "next_stop_mandatory": selection.next_stop_mandatory,
            "alternatives": [
                _alternative_context(alt)
                for alt in selection.alternatives[:max_alternatives]
            ],
            "alternatives_omitted": selection.alternatives_omitted_count
            + max(0, len(selection.alternatives) - max_alternatives),
        }
    if point.lookahead is not None:
        data["lookahead"] = {
            "rule": point.lookahead.rule,
            "station": point.lookahead.station_name,
            "price_difference_per_gallon": _num(
                point.lookahead.price_difference_per_gallon
            ),
            "estimated_savings": _num(point.lookahead.estimated_savings),
            "stop_overhead_cost": _num(point.lookahead.stop_overhead_cost),
        }
    return {k: v for k, v in data.items() if v is not None}


def build_explanation_context(
    result: FuelOptimizationCalculateResponse,
    stop_sequence: int | None = None,
    *,
    max_alternatives: int = MAX_ALTERNATIVES_PER_STOP,
    brief_itinerary: bool = False,
    max_points: int | None = None,
) -> dict[str, Any]:
    summary = result.summary
    context: dict[str, Any] = {
        "status": result.status.value
        if hasattr(result.status, "value")
        else str(result.status),
        "summary": {
            "total_fuel_cost": _num(summary.total_fuel_cost),
            "fuel_purchased_gal": _num(summary.total_fuel_purchased_gallons),
            "fuel_consumed_gal": _num(summary.total_fuel_consumed_gallons),
            "stops": summary.number_of_stops,
            "total_detour_m": _num(summary.total_detour_distance_meters),
            "total_detour_s": summary.total_detour_time_seconds,
            "remaining_fuel_gal": _num(summary.remaining_fuel_gallons),
        },
        "optimizer_explanation": {
            "summary": result.explanation.summary,
            "outcome": result.explanation.outcome,
            "key_points": result.explanation.key_points,
            "warnings": result.explanation.warnings,
            "skipped_stations": [
                {
                    "reason": stat.reason,
                    "map_color": REJECTED_STATION_COLORS.get(stat.reason),
                    "description": stat.description,
                    "count": stat.count,
                }
                for stat in result.explanation.skipped_station_stats
            ],
        },
    }
    if result.economics is not None:
        context["stop_cost_assumptions"] = {
            "downtime_cost_per_hour": _num(result.economics.downtime_cost_per_hour),
            "dwell_minutes": _num(result.economics.dwell_minutes),
            "fixed_stop_cost": _num(result.economics.fixed_stop_cost),
        }
    if result.failure is not None:
        context["failure"] = {
            "reason": str(result.failure.reason),
            "message": result.failure.message,
            "stopped_at_route_offset_m": _num(
                result.failure.stopped_at_route_offset_meters
            ),
            "deficit_gal": _num(result.failure.primary_target.deficit_gallons),
        }

    focused = None
    if stop_sequence is not None:
        focused = next(
            (p for p in result.itinerary if p.sequence == stop_sequence), None
        )
    if focused is not None:
        context["focused_point"] = _point_context(focused, max_alternatives)
        overview = [
            {"sequence": p.sequence, "kind": p.kind, "label": p.label}
            for p in result.itinerary
        ]
        if max_points is not None and len(overview) > max_points:
            context["itinerary_points_omitted"] = len(overview) - max_points
            overview = overview[:max_points]
        context["itinerary_overview"] = overview
    else:
        points = result.itinerary
        if max_points is not None and len(points) > max_points:
            context["itinerary_points_omitted"] = len(points) - max_points
            points = points[:max_points]
        context["itinerary"] = [
            _point_context(p, max_alternatives, brief_itinerary) for p in points
        ]
    return context


def _fit_context(
    result: FuelOptimizationCalculateResponse, stop_sequence: int | None
) -> str:
    """Serialize the context, shrinking it until it fits the LLM request limits."""
    levels: list[dict[str, Any]] = [
        {},
        {"max_alternatives": 3},
        {"max_alternatives": 2, "brief_itinerary": True},
        {"max_alternatives": 1, "brief_itinerary": True, "max_points": 40},
        {"max_alternatives": 0, "brief_itinerary": True, "max_points": 20},
    ]
    text = ""
    for options in levels:
        context = build_explanation_context(result, stop_sequence, **options)
        text = json.dumps(context, ensure_ascii=False, separators=(",", ":"))
        if len(text) <= MAX_CONTEXT_CHARS:
            break
    return text


def build_messages(
    result: FuelOptimizationCalculateResponse,
    *,
    stop_sequence: int | None,
    question: str | None,
    history: list[dict[str, str]],
    language: Literal["en", "ru"],
) -> list[dict[str, str]]:
    context_json = _fit_context(result, stop_sequence)
    has_focus = '"focused_point"' in context_json
    focus_hint = ""
    if has_focus:
        focus_hint = (
            f" The user is looking at itinerary point #{stop_sequence}"
            " (see focused_point)."
        )
    system = SYSTEM_PROMPT.format(
        rejected_colors=", ".join(
            f"{reason}={color}" for reason, color in REJECTED_STATION_COLORS.items()
        ),
        compared_colors=", ".join(
            f"{outcome}={color}" for outcome, color in COMPARED_STATION_COLORS.items()
        ),
        language_name=LANGUAGE_NAMES.get(language, "English"),
        context=context_json,
    )
    language_name = LANGUAGE_NAMES.get(language, "English")
    default_question = DEFAULT_QUESTIONS[language]["stop" if has_focus else "route"]
    # Restating the language next to the question keeps models from following
    # the language of the (English) context or of earlier messages instead.
    user_content = f"{question or default_question}\n\n(Answer in {language_name}.)"
    return [
        {"role": "system", "content": system + focus_hint},
        *history,
        {"role": "user", "content": user_content},
    ]


def build_fallback_answer(
    result: FuelOptimizationCalculateResponse, stop_sequence: int | None
) -> str:
    lines = [result.explanation.summary, result.explanation.outcome]
    lines.extend(result.explanation.key_points)
    point = None
    if stop_sequence is not None:
        point = next((p for p in result.itinerary if p.sequence == stop_sequence), None)
    if point is not None and point.selection is not None:
        selection = point.selection
        lines.append(
            f"{point.label}: sticker price "
            f"${float(selection.sticker_price_per_gallon):.2f}/gal"
            + (
                f", effective price ${float(selection.effective_price_per_gallon):.2f}/gal"
                " including the detour and stop costs."
                if selection.effective_price_per_gallon is not None
                else "."
            )
        )
        for alt in selection.alternatives[:MAX_ALTERNATIVES_PER_STOP]:
            lines.append(f"Not chosen: {alt.name} ({alt.outcome.replace('_', ' ')}).")
    lines.extend(f"Warning: {warning}" for warning in result.explanation.warnings)
    return "\n".join(line for line in lines if line)


class FuelOptimizationExplainer:
    def __init__(self, provider: LLMProvider | None) -> None:
        self._provider = provider

    async def explain(
        self,
        result: FuelOptimizationCalculateResponse,
        *,
        stop_sequence: int | None,
        question: str | None,
        history: list[dict[str, str]],
        language: Literal["en", "ru"],
    ) -> tuple[str, Literal["ai", "fallback"]]:
        """Return (answer, source) where source is "ai" or "fallback"."""
        if self._provider is not None:
            messages = build_messages(
                result,
                stop_sequence=stop_sequence,
                question=question,
                history=history,
                language=language,
            )
            try:
                return await self._provider.complete(messages), "ai"
            except LLMProviderError as exc:
                cause = exc.__cause__
                logger.warning(
                    "LLM explanation failed, using fallback: %s (%s)", exc, cause
                )
        return build_fallback_answer(result, stop_sequence), "fallback"
