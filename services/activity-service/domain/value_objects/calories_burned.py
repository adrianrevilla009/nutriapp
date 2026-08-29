"""CaloriesBurned -- a validated, non-negative calorie-burn figure
(test-plan section 1). Zero is valid (a very light/short activity can
genuinely burn ~0 kcal above baseline); negative is never valid.

Per `.claude/agents/activity-agent.md`'s rule, this value is never
presented as more precise than the source claims -- in this MVP it is
always the user's own estimate, never silently upgraded to a
provider-reported figure (no provider exists yet, implementation plan
section 1).
"""

from __future__ import annotations

from dataclasses import dataclass


class InvalidCaloriesBurnedError(ValueError):
    """Raised when a calorie-burn figure is negative."""


@dataclass(frozen=True, slots=True)
class CaloriesBurned:
    value: float

    def __post_init__(self) -> None:
        if self.value < 0:
            raise InvalidCaloriesBurnedError(f"CaloriesBurned must be non-negative: {self.value!r}")

    def __float__(self) -> float:
        return float(self.value)
