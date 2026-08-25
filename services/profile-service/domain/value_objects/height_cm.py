"""HeightCm value object. Zero framework imports (ADR-0001)."""

from __future__ import annotations

from dataclasses import dataclass


class InvalidHeightError(Exception):
    """Raised when a height value is not strictly positive."""


@dataclass(frozen=True, slots=True)
class HeightCm:
    value: float

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise InvalidHeightError("height_cm must be strictly positive.")

    def __float__(self) -> float:
        return float(self.value)
