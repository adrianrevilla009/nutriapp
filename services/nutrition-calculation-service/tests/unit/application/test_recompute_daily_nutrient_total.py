from __future__ import annotations

import uuid
from datetime import date

import pytest

from application.commands.recompute_daily_nutrient_total import (
    RecomputeDailyNutrientTotalCommand,
    RecomputeDailyNutrientTotalHandler,
)
from tests.fixtures.factories import (
    FakeDailyNutritionTotalRepository,
    FakeNutrientPanelMirrorRepository,
    FakeOutboxRepository,
)

USER_ID = uuid.uuid4()
ENTRY_ID = uuid.uuid4()
TOTAL_DATE = date(2026, 8, 25)
MACROS = {"calories_kcal": 200.0, "protein_g": 10.0, "carbs_g": 20.0, "fat_g": 5.0}


@pytest.fixture
def handler():
    totals = FakeDailyNutritionTotalRepository()
    mirror = FakeNutrientPanelMirrorRepository()
    outbox = FakeOutboxRepository()
    return RecomputeDailyNutrientTotalHandler(totals, mirror, outbox), totals, mirror, outbox


async def test_logged_entry_upserts_total_and_publishes_day_scope_event(handler):
    handler_obj, totals, _mirror, outbox = handler
    command = RecomputeDailyNutrientTotalCommand(
        user_id=USER_ID,
        entry_id=ENTRY_ID,
        total_date=TOTAL_DATE,
        trigger_event_type="FoodEntryLogged",
        correlation_id="corr-1",
        quantity_grams=150.0,
        macros_per_unit=MACROS,
        source_type="catalog_product",
        source_reference_id="product-1",
    )
    result = await handler_obj.handle(command)

    assert result.compute_total().macros.calories_kcal == pytest.approx(300.0)
    assert len(outbox.enqueued) == 1
    event = outbox.enqueued[0]
    assert event.event_type == "NutritionValueRecomputed"
    assert event.payload["scope"] == "day"
    assert event.payload["reason"] == "food_entry_logged"
    stored = await totals.get(USER_ID, TOTAL_DATE)
    assert stored is not None


async def test_catalog_source_with_mirror_match_resolves_micronutrients(handler):
    handler_obj, _totals, mirror, _outbox = handler
    await mirror.upsert("product-1", {"sugars_g": 5.0})
    command = RecomputeDailyNutrientTotalCommand(
        user_id=USER_ID,
        entry_id=ENTRY_ID,
        total_date=TOTAL_DATE,
        trigger_event_type="FoodEntryLogged",
        correlation_id="corr-1",
        quantity_grams=100.0,
        macros_per_unit=MACROS,
        source_type="catalog_product",
        source_reference_id="product-1",
    )
    result = await handler_obj.handle(command)
    day_line = result.compute_total()
    assert day_line.micronutrients_status == "available"
    assert day_line.micronutrients["sugars_g"] == 5.0


async def test_correction_replaces_prior_contribution(handler):
    handler_obj, _totals, _mirror, outbox = handler
    logged = RecomputeDailyNutrientTotalCommand(
        user_id=USER_ID,
        entry_id=ENTRY_ID,
        total_date=TOTAL_DATE,
        trigger_event_type="FoodEntryLogged",
        correlation_id="corr-1",
        quantity_grams=100.0,
        macros_per_unit=MACROS,
        source_type="catalog_product",
        source_reference_id=None,
    )
    await handler_obj.handle(logged)

    corrected_macros = {"calories_kcal": 50.0, "protein_g": 2.0, "carbs_g": 5.0, "fat_g": 1.0}
    corrected = RecomputeDailyNutrientTotalCommand(
        user_id=USER_ID,
        entry_id=ENTRY_ID,
        total_date=TOTAL_DATE,
        trigger_event_type="FoodEntryCorrected",
        correlation_id="corr-2",
        quantity_grams=100.0,
        macros_per_unit=corrected_macros,
        source_type="catalog_product",
        source_reference_id=None,
    )
    result = await handler_obj.handle(corrected)

    assert result.compute_total().macros.calories_kcal == pytest.approx(50.0)
    assert len(outbox.enqueued) == 2
    assert outbox.enqueued[1].payload["reason"] == "food_entry_corrected"


async def test_deletion_removes_entry_from_total(handler):
    handler_obj, totals, _mirror, _outbox = handler
    logged = RecomputeDailyNutrientTotalCommand(
        user_id=USER_ID,
        entry_id=ENTRY_ID,
        total_date=TOTAL_DATE,
        trigger_event_type="FoodEntryLogged",
        correlation_id="corr-1",
        quantity_grams=100.0,
        macros_per_unit=MACROS,
        source_type="catalog_product",
        source_reference_id=None,
    )
    await handler_obj.handle(logged)

    deleted = RecomputeDailyNutrientTotalCommand(
        user_id=USER_ID,
        entry_id=ENTRY_ID,
        total_date=TOTAL_DATE,
        trigger_event_type="FoodEntryDeleted",
        correlation_id="corr-2",
    )
    result = await handler_obj.handle(deleted)

    assert result.compute_total().macros.calories_kcal == 0.0
    stored = await totals.get(USER_ID, TOTAL_DATE)
    assert ENTRY_ID not in stored.entries
