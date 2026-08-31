"""Servings -- number of portions a Recipe's totals are divided across.

Must be a positive integer: a recipe with zero or negative servings has
no meaningful per-serving total (division by zero/negative is nonsensical,
not just "unusual"), so this is rejected at construction, never coerced.
"""

from __future__ import annotations

from dataclasses import dataclass


class InvalidServingsError(ValueError):
    """Raised for a non-positive servings count."""


@dataclass(frozen=True, slots=True)
class Servings:
    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise InvalidServingsError(f"Servings must be a positive integer, got {self.value!r}.")

    def __int__(self) -> int:
        return self.value
