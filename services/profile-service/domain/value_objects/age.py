"""Age value object. Zero framework imports (ADR-0001)."""

from __future__ import annotations

from dataclasses import dataclass

MIN_AGE = 1
MAX_AGE = 120


class InvalidAgeError(Exception):
    """Raised when an age value falls outside the documented bounds."""


@dataclass(frozen=True, slots=True)
class Age:
    value: int

    def __post_init__(self) -> None:
        if not (MIN_AGE <= self.value <= MAX_AGE):
            raise InvalidAgeError(f"age must be between {MIN_AGE} and {MAX_AGE}.")

    def __int__(self) -> int:
        return int(self.value)
