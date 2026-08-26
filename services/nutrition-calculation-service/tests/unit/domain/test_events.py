from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from domain.events.nutrition_target_updated import build_nutrition_target_updated_event
from domain.events.nutrition_value_recomputed import build_nutrition_value_recomputed_event
from domain.value_objects.activity_level import ActivityLevel
from domain.value_objects.goal_type import GoalType
from domain.value_objects.macro_target_range import MacroTargetRange
from domain.value_objects.nutrient_total_line import MacroAmounts, NutrientTotalLine


def test_build_nutrition_value_recomputed_event_shape():
    user_id = uuid.uuid4()
    line = NutrientTotalLine(
        macros=MacroAmounts(calories_kcal=100.0, protein_g=5.0, carbs_g=10.0, fat_g=2.0),
        micronutrients=None,
        micronutrients_status="unavailable",
    )
    event = build_nutrition_value_recomputed_event(
        user_id=user_id,
        scope="day",
        entry_id=None,
        total_date=date(2026, 8, 25),
        line=line,
        confidence_range=None,
        formula_version="2026.1",
        reason="food_entry_logged",
        correlation_id="corr-1",
        recomputed_at=datetime.now(timezone.utc),
    )
    assert event.event_type == "NutritionValueRecomputed"
    assert event.version == 1
    assert event.aggregate_id == str(user_id)
    assert event.payload["macros"]["calories_kcal"] == 100.0
    assert event.payload["micronutrients_status"] == "unavailable"
    assert event.payload["confidence_range"] is None
    assert event.payload["reason"] == "food_entry_logged"


def test_build_nutrition_target_updated_event_shape():
    user_id = uuid.uuid4()
    macro_targets = MacroTargetRange(
        protein_g_min=112.0, protein_g_max=154.0, fat_g_min=48.0, carbs_g=200.0, carbs_floored=False
    )
    event = build_nutrition_target_updated_event(
        user_id=user_id,
        bmr_kcal=1673.75,
        tdee_kcal=2593.0,
        calorie_target_kcal=2093.0,
        macro_targets=macro_targets,
        goal_type=GoalType.LOSE,
        activity_level=ActivityLevel.MODERATE,
        clamped=True,
        clamp_reason="Deficit capped at 1000 kcal/day below TDEE.",
        formula_version="2026.1",
        reason="weight_recorded",
        effective_from=datetime.now(timezone.utc),
        correlation_id="corr-2",
    )
    assert event.event_type == "NutritionTargetUpdated"
    assert event.version == 1
    assert event.payload["goal_type"] == "LOSE"
    assert event.payload["activity_level"] == "MODERATE"
    assert event.payload["activity_adjustment_kcal"] is None
    assert event.payload["clamped"] is True
    assert event.payload["macro_targets"]["carbs_g"] == 200.0
