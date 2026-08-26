"""Quantity -- amount + unit (test-plan section 0/1: unit vocabulary is
g|ml|serving). Zero framework imports (ADR-0001)."""

from __future__ import annotations

from dataclasses import dataclass

SUPPORTED_UNITS = frozenset({"g", "ml", "serving"})


class InvalidQuantityError(Exception):
    """Raised when amount is not positive or unit is unsupported."""


@dataclass(frozen=True, slots=True)
class Quantity:
    amount: float
    unit: str

    def __post_init__(self) -> None:
        if self.amount <= 0:
            raise InvalidQuantityError(f"Quantity amount must be positive, got {self.amount!r}.")
        if self.unit not in SUPPORTED_UNITS:
            raise InvalidQuantityError(f"Unsupported quantity unit: {self.unit!r}.")
