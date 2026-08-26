from datetime import datetime, timezone

from domain.services.product_deduplicator import (
    group_by_dedup_key,
    resolve_dedup_key,
    same_dedup_key,
)
from domain.services.product_normalizer import RawProductRecord
from domain.value_objects.allergen_tags import AllergenTags
from domain.value_objects.barcode import Barcode
from domain.value_objects.dietary_tags import DietaryTags
from domain.value_objects.source_reference import SourceName

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _record(**overrides) -> RawProductRecord:
    defaults = dict(
        source=SourceName.OPEN_FOOD_FACTS,
        source_product_id="off-1",
        barcode=None,
        name="Product",
        brand=None,
        category=None,
        nutrient_panel=None,
        dietary_tags=DietaryTags.empty(),
        allergen_tags=AllergenTags.empty(),
        package_size=None,
        price=None,
        observed_at=NOW,
    )
    defaults.update(overrides)
    return RawProductRecord(**defaults)


def test_same_barcode_different_sources_share_dedup_key():
    a = _record(source=SourceName.OPEN_FOOD_FACTS, barcode=Barcode("5901234123457"))
    b = _record(
        source=SourceName.USDA_FDC, source_product_id="usda-1", barcode=Barcode("5901234123457")
    )
    assert same_dedup_key(a, b)


def test_no_barcode_different_names_never_merged():
    a = _record(source_product_id="off-1", name="Apple Juice")
    b = _record(source_product_id="off-2", name="Orange Juice")
    assert not same_dedup_key(a, b)


def test_no_barcode_same_name_same_source_resync_is_treated_as_update():
    a = _record(source=SourceName.OPEN_FOOD_FACTS, source_product_id="off-1", name="Apple Juice")
    b = _record(source=SourceName.OPEN_FOOD_FACTS, source_product_id="off-1", name="Apple Juice")
    assert same_dedup_key(a, b)


def test_group_by_dedup_key():
    a = _record(source_product_id="off-1", barcode=Barcode("5901234123457"))
    b = _record(
        source=SourceName.USDA_FDC, source_product_id="usda-1", barcode=Barcode("5901234123457")
    )
    c = _record(source_product_id="off-2", name="Unrelated")
    grouped = group_by_dedup_key([a, b, c])
    assert len(grouped) == 2
    assert resolve_dedup_key(a) == resolve_dedup_key(b)
