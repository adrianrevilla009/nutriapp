"""Reference-value tests against the exact published NIH ODS DRI figures
cited in `domain/reference_data/dri_reference_table.py`'s docstring, plus
the `Sex.OTHER` deferral and under-19 absence behaviors required by
`plans/nutrition-calculation-service/dri-rda-addendum.md` sections 1 and 4."""

from __future__ import annotations

import pytest

from domain.services.bmr_calculator import InvalidBiometricInputError
from domain.services.micronutrient_dri_resolver import resolve_micronutrient_dri_minimums
from domain.value_objects.sex import CalculationSexConstant, Sex


def test_male_25yo_gets_the_19_50_band_values():
    result = resolve_micronutrient_dri_minimums(sex=Sex.MALE, age=25)
    assert result == {"calcium_mg": 1000.0, "iron_mg": 8.0, "vitamin_c_mg": 90.0}


def test_female_25yo_gets_the_19_50_band_values_including_the_higher_iron_figure():
    result = resolve_micronutrient_dri_minimums(sex=Sex.FEMALE, age=25)
    assert result == {"calcium_mg": 1000.0, "iron_mg": 18.0, "vitamin_c_mg": 75.0}


def test_age_18_is_excluded_entirely_not_defaulted():
    assert resolve_micronutrient_dri_minimums(sex=Sex.MALE, age=18) == {}
    assert resolve_micronutrient_dri_minimums(sex=Sex.FEMALE, age=18) == {}


def test_age_19_is_the_first_included_age():
    result = resolve_micronutrient_dri_minimums(sex=Sex.MALE, age=19)
    assert result == {"calcium_mg": 1000.0, "iron_mg": 8.0, "vitamin_c_mg": 90.0}


def test_age_50_still_in_the_19_50_band_age_51_moves_to_the_next_band():
    at_50 = resolve_micronutrient_dri_minimums(sex=Sex.FEMALE, age=50)
    at_51 = resolve_micronutrient_dri_minimums(sex=Sex.FEMALE, age=51)
    assert at_50["iron_mg"] == 18.0
    assert at_50["calcium_mg"] == 1000.0
    assert at_51["iron_mg"] == 8.0
    assert at_51["calcium_mg"] == 1200.0


def test_age_70_vs_71_calcium_band_boundary_for_men():
    at_70 = resolve_micronutrient_dri_minimums(sex=Sex.MALE, age=70)
    at_71 = resolve_micronutrient_dri_minimums(sex=Sex.MALE, age=71)
    assert at_70["calcium_mg"] == 1000.0
    assert at_71["calcium_mg"] == 1200.0


def test_vitamin_c_has_a_single_adult_band_unchanged_across_boundaries():
    young_adult = resolve_micronutrient_dri_minimums(sex=Sex.MALE, age=19)
    elderly = resolve_micronutrient_dri_minimums(sex=Sex.MALE, age=90)
    assert young_adult["vitamin_c_mg"] == elderly["vitamin_c_mg"] == 90.0


def test_sex_other_without_override_raises_never_defaults():
    with pytest.raises(InvalidBiometricInputError):
        resolve_micronutrient_dri_minimums(sex=Sex.OTHER, age=30)


def test_sex_other_with_explicit_override_resolves_to_that_constant():
    result = resolve_micronutrient_dri_minimums(
        sex=Sex.OTHER, age=30, calculation_sex_constant=CalculationSexConstant.FEMALE
    )
    assert result == {"calcium_mg": 1000.0, "iron_mg": 18.0, "vitamin_c_mg": 75.0}


def test_under_19_sex_other_with_no_override_returns_empty_not_an_error():
    """Nothing to compute for an under-19 user regardless of sex -- the
    age check must happen before sex resolution so no spurious deferral
    is demanded of a caller with a legitimate under-19 Sex.OTHER user."""
    result = resolve_micronutrient_dri_minimums(sex=Sex.OTHER, age=10)
    assert result == {}


def test_result_never_contains_a_nutrient_outside_the_three_nutrient_scope():
    result = resolve_micronutrient_dri_minimums(sex=Sex.MALE, age=25)
    assert set(result.keys()) == {"calcium_mg", "iron_mg", "vitamin_c_mg"}
