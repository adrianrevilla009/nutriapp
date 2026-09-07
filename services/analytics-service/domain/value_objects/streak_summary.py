"""Result of `domain.services.trend_calculator.compute_streak`.

`sample_size`/`window_days` are structurally required (not optional,
never defaulted) per CLAUDE.md's rule that every computed metric states
its sample size and time window -- construction raises rather than
allowing a caller to build a statistic with that context missing
(test-plan section 1)."""

from __future__ import annotations

from dataclasses import dataclass


class InvalidStreakSummaryError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StreakSummary:
    current_streak_days: int
    sample_size: int
    window_days: int

    def __post_init__(self) -> None:
        if self.sample_size < 0:
            raise InvalidStreakSummaryError("sample_size must be >= 0.")
        if self.window_days <= 0:
            raise InvalidStreakSummaryError("window_days must be > 0.")
        if self.current_streak_days < 0:
            raise InvalidStreakSummaryError("current_streak_days must be >= 0.")
