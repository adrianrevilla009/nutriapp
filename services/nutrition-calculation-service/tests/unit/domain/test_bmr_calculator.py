from __future__ import annotations

import pytest

from domain.services.bmr_calculator import InvalidBiometricInputError, calculate_bmr
from domain.value_objects.sex import CalculationSexConstant, Sex
from tests.fixtures.reference_values import FEMALE_WORKED_EXAMPLE, MALE_WORKED_EXAMPLE


def test_male_worked_example_matches_reference_value():
    example = MALE_WORKED_EXAMPLE
    result = calculate_bmr(
        weight_kg=example["weight_kg"],
        height_cm=example["height_cm"],
        age=example["age"],
        sex=Sex.MALE,
    )
    assert result.bmr_kcal == pytest.approx(example["expected_bmr_kcal"], abs=0.01)
    assert result.sex_constant_used is CalculationSexConstant.MALE


def test_female_worked_example_matches_reference_value():
    example = FEMALE_WORKED_EXAMPLE
    result = calculate_bmr(
        weight_kg=example["weight_kg"],
        height_cm=example["height_cm"],
        age=example["age"],
        sex=Sex.FEMALE,
    )
    assert result.bmr_kcal == pytest.approx(example["expected_bmr_kcal"], abs=0.01)
    assert result.sex_constant_used is CalculationSexConstant.FEMALE


def test_sex_other_without_explicit_constant_raises():
    with pytest.raises(InvalidBiometricInputError):
        calculate_bmr(weight_kg=70, height_cm=175, age=25, sex=Sex.OTHER)


def test_sex_other_with_explicit_constant_computes_and_returns_choice():
    result = calculate_bmr(
        weight_kg=70,
        height_cm=175,
        age=25,
        sex=Sex.OTHER,
        calculation_sex_constant=CalculationSexConstant.FEMALE,
    )
    assert result.sex_constant_used is CalculationSexConstant.FEMALE
    # Same formula as an explicit FEMALE input with identical biometrics.
    female_equivalent = calculate_bmr(weight_kg=70, height_cm=175, age=25, sex=Sex.FEMALE)
    assert result.bmr_kcal == pytest.approx(female_equivalent.bmr_kcal)


@pytest.mark.parametrize(
    "weight_kg,height_cm,age",
    [(0, 175, 25), (-5, 175, 25), (70, 0, 25), (70, -1, 25), (70, 175, 0), (70, 175, -1)],
)
def test_non_positive_inputs_raise(weight_kg, height_cm, age):
    with pytest.raises(InvalidBiometricInputError):
        calculate_bmr(weight_kg=weight_kg, height_cm=height_cm, age=age, sex=Sex.MALE)
