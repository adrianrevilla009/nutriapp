"""Regression guard for `domain.tracked_nutrients.TRACKED_NUTRIENTS` --
addendum 2026-09-12 (`/plans/analytics-service/implementation-plan.md`):
extends coverage to the 3 real, cited micronutrient minimums
`nutrition-calculation-service` now publishes (`calcium_mg`, `iron_mg`,
`vitamin_c_mg`), alongside the pre-existing `protein_g`/`fat_g`.

Asserts the EXACT set, not just "contains" -- catches an accidental
addition of a nutrient `nutrition-calculation-service` doesn't publish a
real, cited minimum for (the addendum's explicit non-goal)."""

from __future__ import annotations

from domain.tracked_nutrients import TRACKED_NUTRIENTS


def test_tracked_nutrients_is_exactly_the_five_nutrients_with_real_target_data():
    assert TRACKED_NUTRIENTS == frozenset(
        {"protein_g", "fat_g", "calcium_mg", "iron_mg", "vitamin_c_mg"}
    )
