"""BMR calculator -- Mifflin-St Jeor equation.

Source: Mifflin MD, St Jeor ST, Hill LA, Scott BJ, Daugherty SA, Koh YO.
"A new predictive equation for resting energy expenditure in healthy
individuals." The American Journal of Clinical Nutrition, 1990;51(2):241-247.

  Men:   BMR = (10 x weight_kg) + (6.25 x height_cm) - (5 x age) + 5
  Women: BMR = (10 x weight_kg) + (6.25 x height_cm) - (5 x age) - 161

`Sex.OTHER` is not addressed by the published formula (which only
distinguishes two sex-linked constants). Per implementation plan Addendum 1
section 9.8, a `Sex.OTHER` user must explicitly select which published
constant to apply for calculation purposes only -- this is never defaulted,
and any user-facing copy must frame it as a limitation of the formula, not
a statement about the user's identity. The selection actually used is
always returned so it can be stored alongside the computed result
(traceability, domain-calculation-conventions SKILL.md section 1).
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.value_objects.sex import CalculationSexConstant, Sex

MALE_CONSTANT_KCAL = 5.0
FEMALE_CONSTANT_KCAL = -161.0


class InvalidBiometricInputError(ValueError):
    """Raised for non-positive weight/height, non-positive age, or a
    `Sex.OTHER` input missing an explicit `calculation_sex_constant`
    selection -- never silently clamped to a default value."""


@dataclass(frozen=True, slots=True)
class BmrResult:
    bmr_kcal: float
    sex_constant_used: CalculationSexConstant


def _resolve_constant(
    sex: Sex, calculation_sex_constant: CalculationSexConstant | None
) -> CalculationSexConstant:
    if sex is Sex.MALE:
        return CalculationSexConstant.MALE
    if sex is Sex.FEMALE:
        return CalculationSexConstant.FEMALE
    if sex is Sex.OTHER:
        if calculation_sex_constant is None:
            raise InvalidBiometricInputError(
                "Sex.OTHER requires an explicit calculation_sex_constant selection "
                "(MALE or FEMALE, for calculation purposes only); it is never defaulted."
            )
        return calculation_sex_constant
    raise InvalidBiometricInputError(f"Unrecognized sex: {sex!r}")


def calculate_bmr(
    *,
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: Sex,
    calculation_sex_constant: CalculationSexConstant | None = None,
) -> BmrResult:
    if weight_kg <= 0:
        raise InvalidBiometricInputError("weight_kg must be positive.")
    if height_cm <= 0:
        raise InvalidBiometricInputError("height_cm must be positive.")
    if age <= 0:
        raise InvalidBiometricInputError("age must be positive.")

    constant_used = _resolve_constant(sex, calculation_sex_constant)
    sex_constant_kcal = (
        MALE_CONSTANT_KCAL if constant_used is CalculationSexConstant.MALE else FEMALE_CONSTANT_KCAL
    )
    bmr_kcal = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age) + sex_constant_kcal
    return BmrResult(bmr_kcal=bmr_kcal, sex_constant_used=constant_used)
