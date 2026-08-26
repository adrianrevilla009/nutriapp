from __future__ import annotations

import pytest

from domain.value_objects.meal_slot import InvalidMealSlotError, MealSlot


@pytest.mark.parametrize("value", ["breakfast", "lunch", "dinner", "snack"])
def test_documented_values_are_valid(value):
    assert MealSlot.from_value(value).value == value


def test_unknown_value_raises():
    with pytest.raises(InvalidMealSlotError):
        MealSlot.from_value("brunch")
