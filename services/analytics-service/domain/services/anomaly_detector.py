"""Pure function evaluating a sustained micronutrient-deficiency breach
over a rolling window (`.claude/agents/analytics-agent.md`'s anomaly/
threshold-detection responsibility), per the approved dev-default rule
(implementation plan section 9 addendum, resolution 2):

  - Only nutrients for which `nutrition-calculation-service` already
    publishes a `target_min` are ever evaluated -- a `None` target_min
    means "excluded", never treated as a pass or a breach.
  - "Sustained breach" = the value is below `target_min` on at least
    `threshold_days` (default 5) of the last `lookback_days` (default 7)
    *calendar days with logged data* -- not 7 elapsed calendar days,
    tolerating gaps in logging.
  - Fewer than `lookback_days` calendar-days-with-data ever recorded for
    that nutrient is a distinct "insufficient sample" result, not
    evaluated as a pass (documents the small-N confidence limitation,
    CLAUDE.md's disclosure rule).

Cooldown/dedup against `anomaly_alerts` is NOT this function's concern --
that depends on persisted state, so it lives in the application layer
(`HandleNutritionValueRecomputedHandler`, test-plan section 2)."""

from __future__ import annotations

from dataclasses import dataclass

from domain.value_objects.trend_point import TrendPoint

DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_THRESHOLD_DAYS = 5


@dataclass(frozen=True, slots=True)
class BreachEvaluation:
    breach: bool
    insufficient_sample: bool
    excluded_no_target: bool
    sample_size: int
    days_below_target: int
    window_days: int


def evaluate_breach(
    nutrient_days: list[TrendPoint],
    target_min: float | None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    threshold_days: int = DEFAULT_THRESHOLD_DAYS,
) -> BreachEvaluation:
    if target_min is None:
        return BreachEvaluation(
            breach=False,
            insufficient_sample=False,
            excluded_no_target=True,
            sample_size=0,
            days_below_target=0,
            window_days=lookback_days,
        )

    most_recent_first = sorted(nutrient_days, key=lambda p: p.on_date, reverse=True)
    recent = most_recent_first[:lookback_days]
    sample_size = len(recent)

    if sample_size < lookback_days:
        return BreachEvaluation(
            breach=False,
            insufficient_sample=True,
            excluded_no_target=False,
            sample_size=sample_size,
            days_below_target=sum(1 for p in recent if p.value < target_min),
            window_days=lookback_days,
        )

    days_below_target = sum(1 for p in recent if p.value < target_min)
    return BreachEvaluation(
        breach=days_below_target >= threshold_days,
        insufficient_sample=False,
        excluded_no_target=False,
        sample_size=sample_size,
        days_below_target=days_below_target,
        window_days=lookback_days,
    )
