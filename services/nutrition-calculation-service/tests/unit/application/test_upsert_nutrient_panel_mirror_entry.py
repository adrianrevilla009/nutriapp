from __future__ import annotations

from application.commands.upsert_nutrient_panel_mirror_entry import (
    UpsertNutrientPanelMirrorEntryCommand,
    UpsertNutrientPanelMirrorEntryHandler,
)
from tests.fixtures.factories import FakeNutrientPanelMirrorRepository


async def test_upserts_translated_canonical_panel():
    mirror = FakeNutrientPanelMirrorRepository()
    handler = UpsertNutrientPanelMirrorEntryHandler(mirror)
    raw = {
        "energy_kcal": 250.0,
        "protein_g": 12.0,
        "carbohydrates_g": 30.0,
        "fat_g": 8.0,
        "sugars_g": 5.0,
    }

    await handler.handle(
        UpsertNutrientPanelMirrorEntryCommand(source_reference_id="p1", nutrition_per_100g=raw)
    )

    stored = await mirror.get_by_reference_id("p1")
    assert stored["calories_kcal"] == 250.0
    assert stored["carbs_g"] == 30.0
    assert stored["sugars_g"] == 5.0


async def test_product_catalogued_then_updated_upserts_in_place():
    mirror = FakeNutrientPanelMirrorRepository()
    handler = UpsertNutrientPanelMirrorEntryHandler(mirror)

    await handler.handle(
        UpsertNutrientPanelMirrorEntryCommand(
            source_reference_id="p1",
            nutrition_per_100g={
                "energy_kcal": 100.0,
                "protein_g": 1.0,
                "carbohydrates_g": 1.0,
                "fat_g": 1.0,
            },
        )
    )
    await handler.handle(
        UpsertNutrientPanelMirrorEntryCommand(
            source_reference_id="p1",
            nutrition_per_100g={
                "energy_kcal": 200.0,
                "protein_g": 2.0,
                "carbohydrates_g": 2.0,
                "fat_g": 2.0,
            },
        )
    )

    stored = await mirror.get_by_reference_id("p1")
    assert stored["calories_kcal"] == 200.0


async def test_no_nutrition_data_is_a_no_op():
    mirror = FakeNutrientPanelMirrorRepository()
    handler = UpsertNutrientPanelMirrorEntryHandler(mirror)

    await handler.handle(
        UpsertNutrientPanelMirrorEntryCommand(source_reference_id="p1", nutrition_per_100g=None)
    )

    assert await mirror.get_by_reference_id("p1") is None
