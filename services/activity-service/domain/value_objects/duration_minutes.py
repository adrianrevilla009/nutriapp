"""DurationMinutes -- a validated, strictly positive exercise duration in
whole minutes (test-plan section 1)."""

from __future__ import annotations

from dataclasses import dataclass


class InvalidDurationError(ValueError):
    """Raised when a duration is not a strictly positive number of minutes."""


@dataclass(frozen=True, slots=True)
class DurationMinutes:
    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise InvalidDurationError(
                f"DurationMinutes must be a strictly positive integer: {self.value!r}"
            )

    def __int__(self) -> int:
        return self.value
