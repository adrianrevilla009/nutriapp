"""WeightKg value object. Zero framework imports (ADR-0001)."""

from __future__ import annotations

from dataclasses import dataclass


class InvalidWeightError(Exception):
    """Raised when a weight value is not strictly positive."""


@dataclass(frozen=True, slots=True)
class WeightKg:
    value: float

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise InvalidWeightError("weight_kg must be strictly positive.")

    def __float__(self) -> float:
        return float(self.value)
