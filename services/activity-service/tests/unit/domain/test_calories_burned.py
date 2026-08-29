"""CaloriesBurned value object tests (test-plan section 1)."""

from __future__ import annotations

import pytest

from domain.value_objects.calories_burned import CaloriesBurned, InvalidCaloriesBurnedError


def test_zero_is_accepted() -> None:
    assert float(CaloriesBurned(0)) == 0.0


def test_negative_raises() -> None:
    with pytest.raises(InvalidCaloriesBurnedError):
        CaloriesBurned(-1)
