"""PortionRangeGrams -- a validated, genuine portion-size range in grams.

media-recognition-conventions SKILL.md's "Estimation Ranges" rule: any
quantitative estimate is inherently approximate and must be presented as a
range, never a single precise number implying false accuracy. A
zero-width "range" (min == max) is itself a false-precision smell and is
rejected, not just min > max.
"""

from __future__ import annotations

from dataclasses import dataclass


class InvalidPortionRangeError(ValueError):
    """Raised when a raw (min_g, max_g) pair is not a genuine, positive
    range with min_g < max_g."""


@dataclass(frozen=True, slots=True)
class PortionRangeGrams:
    min_g: float
    max_g: float

    def __post_init__(self) -> None:
        if self.min_g <= 0 or self.max_g <= 0:
            raise InvalidPortionRangeError(
                f"Portion range bounds must both be positive: min_g={self.min_g!r}, "
                f"max_g={self.max_g!r}"
            )
        if self.min_g >= self.max_g:
            raise InvalidPortionRangeError(
                f"Portion range must be a genuine range (min_g < max_g), got "
                f"min_g={self.min_g!r}, max_g={self.max_g!r}"
            )
