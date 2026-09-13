"""Self-consistency tests for the static DRI reference table -- guards
against a future edit silently introducing an overlapping/missing band, a
negative value, or a row for a nutrient not in `COVERED_NUTRIENTS` (which
would mean it has no cited source per this module's docstring)."""

from __future__ import annotations

from itertools import pairwise

from domain.reference_data.dri_reference_table import (
    COVERED_NUTRIENTS,
    DRI_BANDS,
    DriBand,
)
from domain.value_objects.sex import CalculationSexConstant


def _bands_for(nutrient: str, sex_constant: CalculationSexConstant) -> list[DriBand]:
    return sorted(
        (b for b in DRI_BANDS if b.nutrient == nutrient and b.sex_constant is sex_constant),
        key=lambda b: b.min_age,
    )


def test_every_row_references_a_covered_nutrient():
    for band in DRI_BANDS:
        assert band.nutrient in COVERED_NUTRIENTS


def test_every_covered_nutrient_has_both_sex_constants_represented():
    for nutrient in COVERED_NUTRIENTS:
        represented = {b.sex_constant for b in DRI_BANDS if b.nutrient == nutrient}
        assert represented == {CalculationSexConstant.MALE, CalculationSexConstant.FEMALE}


def test_no_negative_or_zero_values():
    for band in DRI_BANDS:
        assert band.value > 0


def test_bands_start_at_the_adult_floor_of_19_with_no_gap():
    for nutrient in COVERED_NUTRIENTS:
        for sex_constant in (CalculationSexConstant.MALE, CalculationSexConstant.FEMALE):
            bands = _bands_for(nutrient, sex_constant)
            assert bands, f"no bands for {nutrient}/{sex_constant}"
            assert bands[0].min_age == 19


def test_bands_are_contiguous_with_no_gap_or_overlap():
    for nutrient in COVERED_NUTRIENTS:
        for sex_constant in (CalculationSexConstant.MALE, CalculationSexConstant.FEMALE):
            bands = _bands_for(nutrient, sex_constant)
            for earlier, later in pairwise(bands):
                assert earlier.max_age is not None, (
                    f"{nutrient}/{sex_constant} has a non-terminal band with no upper bound"
                )
                assert later.min_age == earlier.max_age + 1, (
                    f"{nutrient}/{sex_constant} has a gap/overlap between "
                    f"{earlier.min_age}-{earlier.max_age} and {later.min_age}"
                )


def test_exactly_one_open_ended_terminal_band_per_nutrient_and_sex():
    for nutrient in COVERED_NUTRIENTS:
        for sex_constant in (CalculationSexConstant.MALE, CalculationSexConstant.FEMALE):
            bands = _bands_for(nutrient, sex_constant)
            open_ended = [b for b in bands if b.max_age is None]
            assert len(open_ended) == 1


def test_no_duplicate_bands():
    seen = set()
    for band in DRI_BANDS:
        key = (band.nutrient, band.sex_constant, band.min_age)
        assert key not in seen, f"duplicate band starting point: {key}"
        seen.add(key)
