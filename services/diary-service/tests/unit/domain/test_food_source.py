from __future__ import annotations

import pytest

from domain.value_objects.food_source import (
    FoodSource,
    FoodSourceSnapshot,
    InvalidFoodSourceError,
)
from domain.value_objects.macro_snapshot import InvalidMacroSnapshotError, MacroSnapshot


def _snapshot(**overrides) -> FoodSourceSnapshot:
    macros = overrides.pop(
        "macros_per_unit",
        MacroSnapshot(calories_kcal=100, protein_g=5, carbs_g=10, fat_g=2),
    )
    defaults = dict(name="Oats", brand="Quaker", quantity=100.0, unit="g")
    defaults.update(overrides)
    return FoodSourceSnapshot(macros_per_unit=macros, **defaults)


def test_valid_catalog_product_source_accepted():
    source = FoodSource(
        source_type="catalog_product", source_reference_id="prod-1", snapshot=_snapshot()
    )
    assert source.source_type == "catalog_product"


def test_missing_source_reference_id_raises():
    with pytest.raises(InvalidFoodSourceError):
        FoodSource(source_type="catalog_product", source_reference_id="", snapshot=_snapshot())


def test_snapshot_with_negative_macro_raises():
    with pytest.raises(InvalidMacroSnapshotError):
        MacroSnapshot(calories_kcal=-1, protein_g=5, carbs_g=10, fat_g=2)


def test_round_trips_through_dict():
    source = FoodSource(
        source_type="catalog_product", source_reference_id="prod-1", snapshot=_snapshot()
    )
    restored = FoodSource.from_dict(source.to_dict())
    assert restored == source
