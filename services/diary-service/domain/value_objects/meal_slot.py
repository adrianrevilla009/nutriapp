"""MealSlot -- test-plan section 0: breakfast|lunch|dinner|snack."""

from __future__ import annotations

from enum import Enum


class InvalidMealSlotError(Exception):
    """Raised when an unknown meal_slot value is supplied."""


class MealSlot(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"

    @classmethod
    def from_value(cls, value: str) -> MealSlot:
        try:
            return cls(value)
        except ValueError as exc:
            raise InvalidMealSlotError(f"Unsupported meal_slot: {value!r}.") from exc
