"""WaterAmountMl -- test-plan section 1: positive value accepted; zero/
negative raises InvalidWaterAmountError."""

from __future__ import annotations

from dataclasses import dataclass


class InvalidWaterAmountError(Exception):
    """Raised when amount_ml is not positive."""


@dataclass(frozen=True, slots=True)
class WaterAmountMl:
    amount_ml: float

    def __post_init__(self) -> None:
        if self.amount_ml <= 0:
            raise InvalidWaterAmountError(f"Water amount must be positive, got {self.amount_ml!r}.")

    def __float__(self) -> float:
        return float(self.amount_ml)
