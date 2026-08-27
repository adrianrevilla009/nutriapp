"""Correction/deletion handling on the DailyNutritionTotal entity itself
(test-plan section 1, nutrient_total_calculator bullet points 5/6) --
these exercise the entity's upsert-by-entry_id / remove-by-entry_id
behavior directly, since that is where correction/deletion semantics
actually live (domain/entities/daily_nutrition_total.py)."""

from __future__ import annotations

import uuid
from datetime import date

from domain.entities.daily_nutrition_total import DailyNutritionTotal
from domain.services.nutrient_total_calculator import calculate_entry_nutrient_total

USER_ID = uuid.uuid4()
ENTRY_ID = uuid.uuid4()
TOTAL_DATE = date(2026, 8, 25)

ORIGINAL_MACROS = {"calories_kcal": 200.0, "protein_g": 10.0, "carbs_g": 20.0, "fat_g": 5.0}
CORRECTED_MACROS = {"calories_kcal": 100.0, "protein_g": 5.0, "carbs_g": 10.0, "fat_g": 2.0}


def _line(macros):
    return calculate_entry_nutrient_total(
        quantity_grams=100.0,
        macros_per_unit=macros,
        source_type="catalog_product",
        micronutrient_panel_per_100g=None,
    )


def test_logged_then_corrected_reflects_only_corrected_values():
    total = DailyNutritionTotal(user_id=USER_ID, total_date=TOTAL_DATE)
    total = total.with_entry_upserted(ENTRY_ID, _line(ORIGINAL_MACROS))
    total = total.with_entry_upserted(ENTRY_ID, _line(CORRECTED_MACROS))

    day_line = total.compute_total()
    assert day_line.macros.calories_kcal == 100.0
    assert len(total.entries) == 1


def test_logged_then_deleted_excludes_entry_entirely():
    total = DailyNutritionTotal(user_id=USER_ID, total_date=TOTAL_DATE)
    total = total.with_entry_upserted(ENTRY_ID, _line(ORIGINAL_MACROS))
    total = total.with_entry_removed(ENTRY_ID)

    day_line = total.compute_total()
    assert day_line.macros.calories_kcal == 0.0
    assert ENTRY_ID not in total.entries


def test_replaying_the_same_logged_event_does_not_double_count():
    total = DailyNutritionTotal(user_id=USER_ID, total_date=TOTAL_DATE)
    total = total.with_entry_upserted(ENTRY_ID, _line(ORIGINAL_MACROS))
    total = total.with_entry_upserted(ENTRY_ID, _line(ORIGINAL_MACROS))

    assert total.compute_total().macros.calories_kcal == 200.0
    assert len(total.entries) == 1
