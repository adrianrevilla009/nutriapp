from datetime import datetime, timezone

import pytest

from domain.services.product_normalizer import (
    EmptyRawRecordError,
    MissingSourceIdentifierError,
    normalize_open_food_facts_record,
    normalize_usda_fdc_record,
)
from domain.value_objects.source_reference import SourceName

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _well_formed_off_record() -> dict:
    return {
        "code": "5901234123457",
        "product_name": "Chocolate Bar",
        "brands": "Acme",
        "categories": "Snacks,Chocolate",
        "nutriments": {
            "energy-kcal_100g": 520,
            "proteins_100g": 6.3,
            "carbohydrates_100g": 58,
            "fat_100g": 28,
            "sugars_100g": 50,
            "fiber_100g": 4,
            "saturated-fat_100g": 16,
            "sodium_100g": 0.1,
            "salt_100g": 0.25,
        },
        "allergens_tags": ["en:gluten", "en:milk"],
        "labels_tags": ["en:organic"],
        "quantity": "100 g",
    }


def _well_formed_usda_record() -> dict:
    return {
        "fdcId": 123456,
        "gtinUpc": "036000291452",
        "description": "Chocolate Bar",
        "brandOwner": "Acme",
        "brandedFoodCategory": "Candy",
        "ingredients": "Sugar, cocoa, milk, wheat flour.",
        "foodNutrients": [
            {"nutrientName": "Energy", "value": 520, "unitName": "KCAL"},
            {"nutrientName": "Protein", "value": 6.3, "unitName": "G"},
            {"nutrientName": "Carbohydrate, by difference", "value": 58, "unitName": "G"},
            {"nutrientName": "Total lipid (fat)", "value": 28, "unitName": "G"},
            {"nutrientName": "Sodium, Na", "value": 100, "unitName": "MG"},
        ],
        "packageWeight": "100 g",
    }


def test_well_formed_off_record_produces_complete_record():
    record = normalize_open_food_facts_record(_well_formed_off_record(), observed_at=NOW)
    assert record.source is SourceName.OPEN_FOOD_FACTS
    assert str(record.barcode) == "5901234123457"
    assert record.name == "Chocolate Bar"
    assert record.nutrient_panel is not None
    assert record.nutrient_panel.energy_kcal == 520
    assert record.category == "Snacks"


def test_well_formed_usda_record_produces_complete_record():
    record = normalize_usda_fdc_record(_well_formed_usda_record(), observed_at=NOW)
    assert record.source is SourceName.USDA_FDC
    assert str(record.barcode) == "036000291452"
    assert record.nutrient_panel is not None
    assert record.nutrient_panel.sodium_mg == 100


def test_off_record_missing_barcode_entirely_proceeds_with_none():
    raw = _well_formed_off_record()
    del raw["code"]
    raw["_id"] = "off-internal-id-1"
    record = normalize_open_food_facts_record(raw, observed_at=NOW)
    assert record.barcode is None


def test_off_record_with_invalid_check_digit_barcode_degrades_to_none():
    raw = _well_formed_off_record()
    raw["code"] = "5901234123456"  # bad check digit
    record = normalize_open_food_facts_record(raw, observed_at=NOW)
    assert record.barcode is None


def test_nutrient_values_as_strings_are_coerced_numerically():
    raw = _well_formed_off_record()
    raw["nutriments"]["proteins_100g"] = "6.3"
    record = normalize_open_food_facts_record(raw, observed_at=NOW)
    assert record.nutrient_panel.protein_g == 6.3


def test_nonnumeric_garbage_nutrient_value_becomes_none_not_a_hard_failure():
    raw = _well_formed_off_record()
    raw["nutriments"]["fiber_100g"] = "n/a"
    record = normalize_open_food_facts_record(raw, observed_at=NOW)
    assert record.nutrient_panel is not None
    assert record.nutrient_panel.fiber_g is None


def test_usda_per_serving_only_data_with_serving_size_converts_to_per_100g():
    raw = _well_formed_usda_record()
    del raw["foodNutrients"]
    raw["servingSize"] = 50
    raw["servingSizeUnit"] = "g"
    raw["labelNutrients"] = {
        "calories": {"value": 260},
        "protein": {"value": 3.15},
        "carbohydrates": {"value": 29},
        "fat": {"value": 14},
        "sodium": {"value": 50},
    }
    record = normalize_usda_fdc_record(raw, observed_at=NOW)
    assert record.nutrient_panel is not None
    assert record.nutrient_panel.energy_kcal == pytest.approx(520.0)


def test_usda_per_serving_only_data_without_serving_size_marks_panel_incomplete():
    raw = _well_formed_usda_record()
    del raw["foodNutrients"]
    raw["labelNutrients"] = {"calories": {"value": 260}}
    record = normalize_usda_fdc_record(raw, observed_at=NOW)
    assert record.nutrient_panel is None


def test_record_entirely_missing_nutrition_panel_allows_name_only_entry():
    raw = _well_formed_off_record()
    del raw["nutriments"]
    record = normalize_open_food_facts_record(raw, observed_at=NOW)
    assert record.nutrient_panel is None
    assert record.name == "Chocolate Bar"


def test_empty_raw_record_raises():
    with pytest.raises(EmptyRawRecordError):
        normalize_open_food_facts_record(None, observed_at=NOW)
    with pytest.raises(EmptyRawRecordError):
        normalize_usda_fdc_record({}, observed_at=NOW)


def test_off_record_missing_identifier_raises():
    with pytest.raises(MissingSourceIdentifierError):
        normalize_open_food_facts_record({"product_name": "Mystery"}, observed_at=NOW)


def test_usda_record_missing_identifier_raises():
    with pytest.raises(MissingSourceIdentifierError):
        normalize_usda_fdc_record({"description": "Mystery"}, observed_at=NOW)
