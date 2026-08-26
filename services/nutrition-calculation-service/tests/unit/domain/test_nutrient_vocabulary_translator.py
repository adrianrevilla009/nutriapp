from __future__ import annotations

from domain.services.nutrient_vocabulary_translator import (
    translate_catalog_nutrition,
    translate_diary_macros,
)


def test_catalog_and_diary_raw_shapes_translate_to_same_canonical_nutrient():
    catalog_raw = {
        "energy_kcal": 250.0,
        "protein_g": 12.0,
        "carbohydrates_g": 30.0,
        "fat_g": 8.0,
        "sugars_g": 5.0,
    }
    diary_raw = {"calories_kcal": 250.0, "protein_g": 12.0, "carbs_g": 30.0, "fat_g": 8.0}

    canonical_from_catalog = translate_catalog_nutrition(catalog_raw)
    canonical_from_diary = translate_diary_macros(diary_raw)

    for field in ("calories_kcal", "protein_g", "carbs_g", "fat_g"):
        assert canonical_from_catalog[field] == canonical_from_diary[field]

    assert canonical_from_catalog["sugars_g"] == 5.0
