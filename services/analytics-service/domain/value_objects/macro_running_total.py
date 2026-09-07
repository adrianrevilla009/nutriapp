"""Result of `domain.services.trend_calculator.compute_running_totals` --
average daily macro/water intake vs. target over a window, always paired
with its `sample_size`/`window_days` (CLAUDE.md's disclosure rule, same
structural guard as `StreakSummary`).

`sample_size == 0` is a valid, distinct state (zero logged days in the
window) -- averages are `None` in that case, never a silently-computed 0
that would read as a real (zero-intake) average (test-plan section 1)."""

from __future__ import annotations

from dataclasses import dataclass


class InvalidMacroRunningTotalError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MacroRunningTotal:
    sample_size: int
    window_days: int
    avg_calories_kcal: float | None
    avg_protein_g: float | None
    avg_carbs_g: float | None
    avg_fat_g: float | None
    avg_water_ml: float | None
    target_calories_kcal: float | None = None

    def __post_init__(self) -> None:
        if self.sample_size < 0:
            raise InvalidMacroRunningTotalError("sample_size must be >= 0.")
        if self.window_days <= 0:
            raise InvalidMacroRunningTotalError("window_days must be > 0.")
        if self.sample_size == 0:
            averages = (
                self.avg_calories_kcal,
                self.avg_protein_g,
                self.avg_carbs_g,
                self.avg_fat_g,
                self.avg_water_ml,
            )
            if any(average is not None for average in averages):
                raise InvalidMacroRunningTotalError(
                    "sample_size == 0 must never carry a computed average."
                )
