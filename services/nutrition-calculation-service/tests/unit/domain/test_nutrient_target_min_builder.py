"""Unit tests for `build_nutrient_targets_min` -- the nutrient-keyed
minimum-target map generalizing `MacroTargetRange`'s already-computed
protein/fat minimums (see the function's own docstring for the full
"what is/isn't covered" reasoning; this test file guards that reasoning
structurally so a future change can't silently start fabricating
micronutrient thresholds without a test failing first).
"""

from __future__ import annotations

from domain.services.nutrient_target_min_builder import (
    NOT_YET_COVERED_NUTRIENTS,
    build_nutrient_targets_min,
)
from domain.value_objects.macro_target_range import MacroTargetRange


def _macro_targets(**overrides: float) -> MacroTargetRange:
    defaults = dict(
        protein_g_min=112.0,
        protein_g_max=154.0,
        fat_g_min=46.5,
        carbs_g=200.0,
        carbs_floored=False,
    )
    defaults.update(overrides)
    return MacroTargetRange(**defaults)  # type: ignore[arg-type]


def test_includes_protein_and_fat_minimums_using_canonical_nutrient_keys():
    macro_targets = _macro_targets(protein_g_min=112.0, fat_g_min=46.5)

    result = build_nutrient_targets_min(macro_targets)

    assert result == {"protein_g": 112.0, "fat_g": 46.5}


def test_reflects_the_macro_targets_passed_in_exactly_no_rounding_or_derivation():
    macro_targets = _macro_targets(protein_g_min=88.25, fat_g_min=33.75)

    result = build_nutrient_targets_min(macro_targets)

    assert result["protein_g"] == 88.25
    assert result["fat_g"] == 33.75


def test_never_includes_a_fabricated_micronutrient_minimum():
    macro_targets = _macro_targets()

    result = build_nutrient_targets_min(macro_targets)

    for nutrient in NOT_YET_COVERED_NUTRIENTS:
        assert nutrient not in result


def test_result_has_exactly_two_keys_today():
    """Documents the current, honest scope explicitly: this is not a
    generic "all nutrients" map yet -- exactly protein_g/fat_g, no more,
    no less, until real reference data exists for anything else."""
    macro_targets = _macro_targets()

    result = build_nutrient_targets_min(macro_targets)

    assert set(result.keys()) == {"protein_g", "fat_g"}
