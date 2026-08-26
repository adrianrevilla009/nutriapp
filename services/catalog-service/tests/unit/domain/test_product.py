from datetime import datetime, timedelta, timezone

import pytest

from domain.entities.product import InvalidProductError, Product
from domain.services.product_normalizer import RawProductRecord
from domain.value_objects.allergen_tags import AllergenTag, AllergenTags
from domain.value_objects.barcode import Barcode
from domain.value_objects.dietary_tags import DietaryTags
from domain.value_objects.nutrient_panel import NutrientPanel
from domain.value_objects.source_reference import SourceName

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
T1 = T0 + timedelta(days=1)


def _record(**overrides) -> RawProductRecord:
    defaults = dict(
        source=SourceName.OPEN_FOOD_FACTS,
        source_product_id="off-1",
        barcode=Barcode("5901234123457"),
        name="Chocolate Bar",
        brand="Acme",
        category="Snacks",
        nutrient_panel=NutrientPanel(energy_kcal=500, protein_g=5, carbohydrates_g=50, fat_g=20),
        dietary_tags=DietaryTags.empty(),
        allergen_tags=AllergenTags.empty(),
        package_size=None,
        price=None,
        observed_at=T0,
    )
    defaults.update(overrides)
    return RawProductRecord(**defaults)


def test_construct_product_from_complete_valid_fields_succeeds():
    record = _record()
    product = Product.from_first_record(product_id=__import__("uuid").uuid4(), record=record)
    assert product.name == "Chocolate Bar"


def test_construct_product_with_no_barcode_and_no_name_raises():
    import uuid

    record = _record(barcode=None, name=None)
    with pytest.raises(InvalidProductError):
        Product.from_first_record(product_id=uuid.uuid4(), record=record)


def test_merge_new_product_from_none_is_new_and_emits_no_changed_fields():
    result = Product.merge(existing=None, incoming=_record())
    assert result.is_new is True
    assert result.changed_fields == ()
    assert result.product.name == "Chocolate Bar"


def test_merge_same_source_resync_with_new_values_wins_for_that_source():
    first = Product.merge(existing=None, incoming=_record(observed_at=T0)).product
    updated_record = _record(observed_at=T1, name="Chocolate Bar Deluxe")
    result = Product.merge(existing=first, incoming=updated_record)
    assert result.is_new is False
    assert "name" in result.changed_fields
    assert result.product.name == "Chocolate Bar Deluxe"


def test_merge_new_source_agreeing_on_nutrition_gains_source_no_conflict():
    first = Product.merge(existing=None, incoming=_record(observed_at=T0)).product
    incoming = _record(
        source=SourceName.USDA_FDC,
        source_product_id="usda-1",
        observed_at=T1,
        nutrient_panel=NutrientPanel(energy_kcal=500, protein_g=5, carbohydrates_g=50, fat_g=20),
    )
    result = Product.merge(existing=first, incoming=incoming)
    assert SourceName.USDA_FDC in result.product.sources
    assert "nutrient_panel" not in result.changed_fields


def test_merge_new_source_disagreeing_on_nutrition_most_recent_wins():
    first = Product.merge(existing=None, incoming=_record(observed_at=T0)).product
    incoming = _record(
        source=SourceName.USDA_FDC,
        source_product_id="usda-1",
        observed_at=T1,
        nutrient_panel=NutrientPanel(energy_kcal=999, protein_g=9, carbohydrates_g=90, fat_g=40),
    )
    result = Product.merge(existing=first, incoming=incoming)
    assert result.product.nutrient_panel.energy_kcal == 999
    assert "nutrient_panel" in result.changed_fields
    # Both sources' raw values remain independently retrievable.
    assert first.source_snapshots[SourceName.OPEN_FOOD_FACTS].nutrient_panel.energy_kcal == 500
    assert result.product.source_snapshots[SourceName.USDA_FDC].nutrient_panel.energy_kcal == 999


def test_merge_no_op_when_incoming_identical_to_stored():
    first = Product.merge(existing=None, incoming=_record(observed_at=T0)).product
    result = Product.merge(existing=first, incoming=_record(observed_at=T0))
    assert result.changed_fields == ()
    assert result.product is first


def test_merge_conflicting_allergen_info_unions_not_intersects():
    off_record = _record(allergen_tags=AllergenTags(frozenset({AllergenTag.GLUTEN})))
    first = Product.merge(existing=None, incoming=off_record).product
    usda_record = _record(
        source=SourceName.USDA_FDC,
        source_product_id="usda-1",
        observed_at=T1,
        allergen_tags=AllergenTags.empty(),
    )
    result = Product.merge(existing=first, incoming=usda_record)
    assert AllergenTag.GLUTEN in result.product.allergen_tags
