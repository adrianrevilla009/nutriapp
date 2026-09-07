"""Result of `domain.services.anomaly_detector.evaluate_breach` when a
sustained breach is found -- the value `HandleNutritionValueRecomputedHandler`
turns into a `NutrientDeficiencyDetected` event (subject to the 14-day
cooldown checked at the application layer, implementation plan section 9
addendum resolution 2).

`disclaimer` is a structurally required, non-empty field -- CLAUDE.md
section 8's professional-advice boundary, applied here by the same
underlying principle even though this isn't `nutrition-assistant-service`
(resolution 2). This is never optional/defaultable to an empty string."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_DISCLAIMER = (
    "This is an informational pattern detected in your own logged data, "
    "not a medical diagnosis -- consult a qualified healthcare professional."
)


class InvalidDeficiencySignalError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DeficiencySignal:
    nutrient: str
    value: float
    target_min: float
    window_days: int
    sample_size: int
    disclaimer: str = DEFAULT_DISCLAIMER

    def __post_init__(self) -> None:
        if not self.nutrient:
            raise InvalidDeficiencySignalError("nutrient must be non-empty.")
        if self.sample_size < 0:
            raise InvalidDeficiencySignalError("sample_size must be >= 0.")
        if self.window_days <= 0:
            raise InvalidDeficiencySignalError("window_days must be > 0.")
        if not self.disclaimer or not self.disclaimer.strip():
            raise InvalidDeficiencySignalError(
                "disclaimer must be a non-empty, non-diagnosis-framed string."
            )
