"""Pure functions computing rolling trends -- streaks, running totals,
consistency over time (`.claude/agents/analytics-agent.md`'s domain
responsibilities). Zero I/O, zero framework dependency (ADR-0001):
callers (application-layer query handlers) are responsible for fetching
an already-windowed, bounded row set from a repository and mapping it
into the shapes below before calling in here -- CLAUDE.md's pagination
rule ("queries over long historical windows must be paginated/optimized,
not load full history into memory") is enforced by the *caller*, not by
these functions refusing arbitrarily large input.

Every returned value object carries `sample_size`/`window_days`
structurally (CLAUDE.md's disclosure rule -- see
`domain/value_objects/streak_summary.py`/`macro_running_total.py`)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from domain.value_objects.macro_running_total import MacroRunningTotal
from domain.value_objects.streak_summary import StreakSummary


@dataclass(frozen=True, slots=True)
class DailyMacroTotals:
    """One `daily_log_summary` row, already mapped out of the ORM/repository
    layer -- the domain layer never sees `infrastructure.persistence.models`."""

    on_date: date
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    water_ml: float


def compute_streak(logged_dates: list[date], window_days: int, as_of: date) -> StreakSummary:
    """`current_streak_days` counts consecutive logged days ending exactly
    at `as_of` -- if `as_of` itself has no logged data, the streak is 0
    (today not yet logged breaks the streak, it does not roll over to
    yesterday's count)."""
    if window_days <= 0:
        raise ValueError("window_days must be > 0.")

    window_start = as_of - timedelta(days=window_days - 1)
    in_window = {d for d in logged_dates if window_start <= d <= as_of}

    streak = 0
    cursor = as_of
    while cursor in in_window:
        streak += 1
        cursor -= timedelta(days=1)

    return StreakSummary(
        current_streak_days=streak, sample_size=len(in_window), window_days=window_days
    )


def compute_running_totals(
    daily_rows: list[DailyMacroTotals],
    window_days: int,
    target_calories_kcal: float | None = None,
) -> MacroRunningTotal:
    """Average daily macro/water intake over the given (already-windowed)
    rows. `sample_size == 0` returns `None` averages rather than a
    silently-computed 0 (test-plan section 1's explicit requirement --
    zero logged days must never look like a real zero-intake average)."""
    if window_days <= 0:
        raise ValueError("window_days must be > 0.")

    sample_size = len(daily_rows)
    if sample_size == 0:
        return MacroRunningTotal(
            sample_size=0,
            window_days=window_days,
            avg_calories_kcal=None,
            avg_protein_g=None,
            avg_carbs_g=None,
            avg_fat_g=None,
            avg_water_ml=None,
            target_calories_kcal=target_calories_kcal,
        )

    return MacroRunningTotal(
        sample_size=sample_size,
        window_days=window_days,
        avg_calories_kcal=sum(r.calories_kcal for r in daily_rows) / sample_size,
        avg_protein_g=sum(r.protein_g for r in daily_rows) / sample_size,
        avg_carbs_g=sum(r.carbs_g for r in daily_rows) / sample_size,
        avg_fat_g=sum(r.fat_g for r in daily_rows) / sample_size,
        avg_water_ml=sum(r.water_ml for r in daily_rows) / sample_size,
        target_calories_kcal=target_calories_kcal,
    )
