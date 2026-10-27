from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.fuel_optimization.dependencies import get_fuel_optimization_explainer
from app.fuel_optimization.explain import (
    FuelOptimizationExplainer,
    build_explanation_context,
    build_messages,
)
from app.fuel_optimization.schemas import FuelOptimizationCalculateResponse
from app.llm import LLMProvider, LLMProviderError
from app.main import app


def _result() -> FuelOptimizationCalculateResponse:
    station_id = str(uuid.uuid4())
    return FuelOptimizationCalculateResponse.model_validate(
        {
            "route_id": str(uuid.uuid4()),
            "vehicle_id": str(uuid.uuid4()),
            "optimization_run_id": str(uuid.uuid4()),
            "status": "success",
            "algorithm": "greedy",
            "algorithm_version": "1",
            "summary": {
                "total_fuel_consumed_gallons": "100",
                "total_fuel_purchased_gallons": "60",
                "total_fuel_cost": "240",
                "total_detour_distance_meters": "1000",
                "total_detour_time_seconds": 120,
                "number_of_stops": 1,
                "remaining_fuel_gallons": "20",
            },
            "stops": [],
            "itinerary": [
                {
                    "sequence": 1,
                    "kind": "refuel",
                    "status": "reached",
                    "label": "Pilot",
                    "station_id": station_id,
                    "route_offset_meters": "5000",
                    "coordinate": ["40", "-93"],
                    "fuel_price_per_gallon": "4.0",
                    "selection": {
                        "rule": "lowest_effective_price",
                        "sticker_price_per_gallon": "4.0",
                        "detour_fuel_gallons": "0.1",
                        "detour_fuel_cost": "0.4",
                        "time_cost": "0",
                        "fixed_stop_cost": "0",
                        "alternatives": [
                            {
                                "station_id": str(uuid.uuid4()),
                                "name": "Loves",
                                "latitude": "40",
                                "longitude": "-93",
                                "route_offset_meters": "5200",
                                "fuel_price_per_gallon": "4.5",
                                "detour_distance_meters": "300",
                                "detour_time_seconds": 30,
                                "cheaper_by_sticker": False,
                                "outcome": "higher_effective_price",
                            }
                        ],
                    },
                },
                {
                    "sequence": 2,
                    "kind": "destination",
                    "status": "reached",
                    "label": "Destination",
                    "route_offset_meters": "9000",
                    "coordinate": ["41", "-92"],
                },
            ],
            "failure": None,
            "explanation": {
                "summary": "One stop at Pilot.",
                "outcome": "Destination reached.",
                "key_points": ["Pilot was the cheapest."],
                "warnings": [],
                "skipped_station_stats": [
                    {
                        "reason": "missing_diesel_price",
                        "description": "No diesel price",
                        "count": 3,
                    }
                ],
            },
        }
    )


class FakeProvider(LLMProvider):
    def __init__(self, error: bool = False) -> None:
        self.error = error
        self.messages: list[dict[str, str]] = []

    def get_name(self) -> str:
        return "fake"

    async def complete(self, messages: list[dict[str, str]]) -> str:
        self.messages = messages
        if self.error:
            raise LLMProviderError("boom")
        return "Because Pilot is cheaper."


def test_context_focuses_on_one_stop_and_includes_colors() -> None:
    context = build_explanation_context(_result(), stop_sequence=1)

    assert context["focused_point"]["label"] == "Pilot"
    alternative = context["focused_point"]["why_chosen"]["alternatives"][0]
    assert alternative["map_color"] == "red"
    assert context["optimizer_explanation"]["skipped_stations"][0]["map_color"] == (
        "orange"
    )
    assert "itinerary" not in context


def test_context_without_focus_lists_whole_itinerary() -> None:
    context = build_explanation_context(_result())

    assert [p["sequence"] for p in context["itinerary"]] == [1, 2]
    assert "focused_point" not in context


def test_messages_end_with_question_after_history() -> None:
    messages = build_messages(
        _result(),
        stop_sequence=None,
        question="Why not Loves?",
        history=[{"role": "user", "content": "hi"}],
        language="ru",
    )

    assert messages[0]["role"] == "system"
    assert "Loves" in messages[0]["content"]
    assert "Always answer in Russian" in messages[0]["content"]
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"].startswith("Why not Loves?")
    assert "Answer in Russian" in messages[-1]["content"]


async def test_explainer_uses_provider() -> None:
    provider = FakeProvider()
    answer, source = await FuelOptimizationExplainer(provider).explain(
        _result(), stop_sequence=1, question=None, history=[], language="en"
    )

    assert (answer, source) == ("Because Pilot is cheaper.", "ai")
    assert provider.messages[-1]["content"].startswith("Explain why")


@pytest.mark.parametrize("provider", [None, FakeProvider(error=True)])
async def test_explainer_falls_back_without_working_provider(
    provider: LLMProvider | None,
) -> None:
    answer, source = await FuelOptimizationExplainer(provider).explain(
        _result(), stop_sequence=1, question=None, history=[], language="en"
    )

    assert source == "fallback"
    assert "One stop at Pilot." in answer
    assert "Loves" in answer


def test_explain_endpoint(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    app.dependency_overrides[get_fuel_optimization_explainer] = lambda: (
        FuelOptimizationExplainer(FakeProvider())
    )
    try:
        payload: dict[str, Any] = {
            "optimization": _result().model_dump(mode="json"),
            "stop_sequence": 1,
            "question": "Why this one?",
        }
        response = client.post(
            f"{settings.API_V1_STR}/fuel-optimization/explain",
            headers=superuser_token_headers,
            json=payload,
        )
    finally:
        app.dependency_overrides.pop(get_fuel_optimization_explainer, None)

    assert response.status_code == 200
    assert response.json() == {"answer": "Because Pilot is cheaper.", "source": "ai"}
