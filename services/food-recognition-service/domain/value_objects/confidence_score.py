"""ConfidenceScore -- a validated confidence value in [0.0, 1.0].

Every detection this service returns carries an explicit confidence score
(media-recognition-conventions SKILL.md's "Confidence Must Always Be
Explicit") -- never a silent high/low guess.
"""

from __future__ import annotations

from dataclasses import dataclass


class InvalidConfidenceScoreError(ValueError):
    """Raised when a raw float is outside the valid [0.0, 1.0] range."""


@dataclass(frozen=True, slots=True)
class ConfidenceScore:
    value: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 1.0):
            raise InvalidConfidenceScoreError(
                f"ConfidenceScore must be within [0.0, 1.0]: {self.value!r}"
            )

    def __float__(self) -> float:
        return self.value
