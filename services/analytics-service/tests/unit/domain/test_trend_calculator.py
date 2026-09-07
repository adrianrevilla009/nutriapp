from __future__ import annotations

from datetime import date, timedelta

import pytest

from domain.services.trend_calculator import (
    DailyMacroTotals,
    compute_running_totals,
    compute_streak,
)

TODAY = date(2026, 6, 8)


def _days_ago(n: int) -> date:
    return TODAY - timedelta(days=n)


def test_streak_small_n_three_logged_days_two_consecutive_ending_today():
    logged_dates = [TODAY, _days_ago(1), _days_ago(5)]
    result = compute_streak(logged_dates, window_days=7, as_of=TODAY)

    assert result.current_streak_days == 2
    assert result.sample_size == 3
    assert result.window_days == 7


def test_streak_large_n_sixty_days_with_three_gaps():
    window_days = 60
    logged_dates = [_days_ago(n) for n in range(window_days) if n not in (10, 25, 40)]
    result = compute_streak(logged_dates, window_days=window_days, as_of=TODAY)

    assert result.sample_size == window_days - 3
    # Consecutive run ending today is broken only by the nearest gap, at day 10.
    assert result.current_streak_days == 10


def test_streak_today_not_logged_breaks_streak_to_zero():
    logged_dates = [_days_ago(1), _days_ago(2)]
    result = compute_streak(logged_dates, window_days=7, as_of=TODAY)

    assert result.current_streak_days == 0
    assert result.sample_size == 2


def test_streak_rejects_non_positive_window():
    with pytest.raises(ValueError):
        compute_streak([TODAY], window_days=0, as_of=TODAY)


def test_running_totals_empty_input_returns_none_averages_not_zero():
    result = compute_running_totals([], window_days=7)

    assert result.sample_size == 0
    assert result.window_days == 7
    assert result.avg_calories_kcal is None
    assert result.avg_protein_g is None
    assert result.avg_carbs_g is None
    assert result.avg_fat_g is None
    assert result.avg_water_ml is None


def test_running_totals_small_n_two_days():
    rows = [
        DailyMacroTotals(
            TODAY, calories_kcal=2000, protein_g=100, carbs_g=200, fat_g=60, water_ml=1500
        ),
        DailyMacroTotals(
            _days_ago(1), calories_kcal=1800, protein_g=90, carbs_g=180, fat_g=50, water_ml=1000
        ),
    ]
    result = compute_running_totals(rows, window_days=7, target_calories_kcal=2100)

    assert result.sample_size == 2
    assert result.window_days == 7
    assert result.avg_calories_kcal == pytest.approx(1900.0)
    assert result.avg_protein_g == pytest.approx(95.0)
    assert result.avg_water_ml == pytest.approx(1250.0)
    assert result.target_calories_kcal == 2100


def test_running_totals_large_n_thirty_days():
    rows = [
        DailyMacroTotals(
            _days_ago(n),
            calories_kcal=2000.0,
            protein_g=100.0,
            carbs_g=200.0,
            fat_g=60.0,
            water_ml=2000.0,
        )
        for n in range(30)
    ]
    result = compute_running_totals(rows, window_days=30)

    assert result.sample_size == 30
    assert result.avg_calories_kcal == pytest.approx(2000.0)
    assert result.avg_water_ml == pytest.approx(2000.0)


def test_running_totals_rejects_non_positive_window():
    with pytest.raises(ValueError):
        compute_running_totals([], window_days=0)
