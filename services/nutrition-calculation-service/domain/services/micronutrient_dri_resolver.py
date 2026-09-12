"""Resolves a user's per-nutrient RDA/DRI minimum for calcium_mg, iron_mg,
vitamin_c_mg from the static reference table in
`domain/reference_data/dri_reference_table.py` -- see that module's
docstring for the exact source citations and figures. Pure function, zero
framework dependencies (ADR-0001).

`Sex.OTHER` handling mirrors `bmr_calculator.py`'s `_resolve_constant`
exactly: MALE/FEMALE always resolve to their own constant; `Sex.OTHER`
requires an explicit `calculation_sex_constant` selection and raises the
*same* `InvalidBiometricInputError` type `bmr_calculator.py` raises when it
is missing -- never defaulted, never averaged. In this service's actual
production call path (`RecomputeNutritionTargetHandler.handle`), this
function is always called with `calculation_sex_constant=<the BMR
calculator's already-resolved sex_constant_used>`, so this branch is
unreachable there by construction; it exists so this module stays a
correct, independently-safe pure function on its own (callable directly,
as this module's own unit tests do), not one that is only safe because of
how its one current caller happens to use it.

Ages below 19 return an empty dict -- absent, not defaulted -- checked
*before* sex resolution, so an under-19 `Sex.OTHER` user with no override
does not spuriously raise: there is nothing to compute for them regardless
of sex, so no explicit sex selection is demanded that the caller has no
reason to supply.
"""

from __future__ import annotations

from domain.reference_data.dri_reference_table import DRI_BANDS
from domain.services.bmr_calculator import InvalidBiometricInputError
from domain.value_objects.sex import CalculationSexConstant, Sex

ADULT_MIN_AGE = 19


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


def resolve_micronutrient_dri_minimums(
    *,
    sex: Sex,
    age: int,
    calculation_sex_constant: CalculationSexConstant | None = None,
) -> dict[str, float]:
    """Returns `{"calcium_mg": ..., "iron_mg": ..., "vitamin_c_mg": ...}`
    for an adult (age >= 19) whose sex/calculation-sex-constant resolves
    cleanly. Returns `{}` for age < 19 (absent, not defaulted -- DRI
    child/adolescent tables use fundamentally different bands, out of
    scope per the addendum). Raises `InvalidBiometricInputError` for
    `Sex.OTHER` with no explicit `calculation_sex_constant` -- the caller
    must defer the whole recompute, never silently drop just the
    micronutrient entries."""
    if age < ADULT_MIN_AGE:
        return {}

    resolved_constant = _resolve_constant(sex, calculation_sex_constant)

    result: dict[str, float] = {}
    for band in DRI_BANDS:
        if band.sex_constant is not resolved_constant:
            continue
        if age < band.min_age:
            continue
        if band.max_age is not None and age > band.max_age:
            continue
        result[band.nutrient] = band.value
    return result
