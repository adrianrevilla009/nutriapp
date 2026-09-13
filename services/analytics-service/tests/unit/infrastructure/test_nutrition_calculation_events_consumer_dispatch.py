"""Unit-level (no Postgres/RabbitMQ, no Docker) coverage of
`dispatch_nutrition_calculation_event`'s `NutritionTargetUpdated` branch --
specifically the `nutrient_targets_min`/`macro_targets` field-resolution
logic added by the addendum 2026-09-12. The real-RabbitMQ, real-Postgres
version of these same scenarios lives in
`tests/integration/infrastructure/test_nutrition_calculation_events_consumer.py`
(requires Docker, not runnable in every environment) -- this module
exercises the identical branch logic against fakes, monkeypatching the two
concrete Postgres repository classes the dispatch function constructs
internally."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from infrastructure.messaging.nutrition_calculation_events_consumer import (
    dispatch_nutrition_calculation_event,
)
from tests.fixtures.factories import (
    FakeMicronutrientWindowRepository,
    FakeProcessedNutritionCalculationEventsRepository,
)

pytestmark = pytest.mark.asyncio

_MODULE = "infrastructure.messaging.nutrition_calculation_events_consumer"


def _base_payload(user_id: uuid.UUID, **overrides) -> dict:
    payload = {
        "user_id": str(user_id),
        "bmr_kcal": 1600.0,
        "tdee_kcal": 2200.0,
        "calorie_target_kcal": 2000.0,
        "macro_targets": {
            "protein_g_min": 50.0,
            "protein_g_max": 150.0,
            "fat_g_min": 44.0,
            "carbs_g": 250.0,
        },
        "goal_type": "MAINTAIN",
        "activity_level": "MODERATE",
        "activity_adjustment_kcal": None,
        "clamped": False,
        "clamp_reason": None,
        "formula_version": "v1",
        "reason": "weight_recorded",
        "effective_from": "2026-06-08T07:01:00+00:00",
    }
    payload.update(overrides)
    return payload


async def _dispatch_target_updated(payload: dict, window: FakeMicronutrientWindowRepository):
    processed = FakeProcessedNutritionCalculationEventsRepository()
    with (
        patch(f"{_MODULE}.PostgresProcessedNutritionCalculationEventsRepository", return_value=processed),
        patch(f"{_MODULE}.PostgresMicronutrientWindowRepository", return_value=window),
    ):
        await dispatch_nutrition_calculation_event(
            session=None,  # unused -- both repositories above are faked
            event_type="NutritionTargetUpdated",
            event_id=uuid.uuid4(),
            payload=payload,
            metadata={"correlation_id": "corr-1"},
        )


async def test_dispatch_resolves_all_five_targets_from_nutrient_targets_min():
    window = FakeMicronutrientWindowRepository()
    user_id = uuid.uuid4()
    payload = _base_payload(
        user_id,
        nutrient_targets_min={
            "protein_g": 55.0,
            "fat_g": 40.0,
            "calcium_mg": 1000.0,
            "iron_mg": 8.0,
            "vitamin_c_mg": 90.0,
        },
    )

    await _dispatch_target_updated(payload, window)

    assert await window.get_current_target_min(user_id, "protein_g") == 55.0
    assert await window.get_current_target_min(user_id, "fat_g") == 40.0
    assert await window.get_current_target_min(user_id, "calcium_mg") == 1000.0
    assert await window.get_current_target_min(user_id, "iron_mg") == 8.0
    assert await window.get_current_target_min(user_id, "vitamin_c_mg") == 90.0


async def test_dispatch_falls_back_to_macro_targets_when_nutrient_targets_min_absent():
    """Backward compatibility: an event published before `nutrient_targets_min`
    existed at all still resolves protein_g/fat_g via `macro_targets`; the 3
    newer keys resolve to None, never fabricated."""
    window = FakeMicronutrientWindowRepository()
    user_id = uuid.uuid4()
    payload = _base_payload(user_id)  # no nutrient_targets_min key at all

    await _dispatch_target_updated(payload, window)

    assert await window.get_current_target_min(user_id, "protein_g") == 50.0
    assert await window.get_current_target_min(user_id, "fat_g") == 44.0
    assert await window.get_current_target_min(user_id, "calcium_mg") is None
    assert await window.get_current_target_min(user_id, "iron_mg") is None
    assert await window.get_current_target_min(user_id, "vitamin_c_mg") is None


async def test_dispatch_under_19_user_has_none_for_dri_gated_keys():
    """`nutrient_targets_min` present but only carrying protein_g/fat_g
    (e.g. no resolved DRI minimum for this user) -- the 3 newer keys
    resolve to None, not defaulted."""
    window = FakeMicronutrientWindowRepository()
    user_id = uuid.uuid4()
    payload = _base_payload(user_id, nutrient_targets_min={"protein_g": 50.0, "fat_g": 44.0})

    await _dispatch_target_updated(payload, window)

    assert await window.get_current_target_min(user_id, "protein_g") == 50.0
    assert await window.get_current_target_min(user_id, "fat_g") == 44.0
    assert await window.get_current_target_min(user_id, "calcium_mg") is None
    assert await window.get_current_target_min(user_id, "iron_mg") is None
    assert await window.get_current_target_min(user_id, "vitamin_c_mg") is None


async def test_dispatch_prefers_nutrient_targets_min_over_macro_targets_for_protein_and_fat():
    """When both are present, `nutrient_targets_min` is the canonical
    source for protein_g/fat_g too (macro_targets is only a fallback)."""
    window = FakeMicronutrientWindowRepository()
    user_id = uuid.uuid4()
    payload = _base_payload(
        user_id, nutrient_targets_min={"protein_g": 999.0, "fat_g": 888.0}
    )
    # macro_targets on this payload still says protein_g_min=50.0/fat_g_min=44.0

    await _dispatch_target_updated(payload, window)

    assert await window.get_current_target_min(user_id, "protein_g") == 999.0
    assert await window.get_current_target_min(user_id, "fat_g") == 888.0
