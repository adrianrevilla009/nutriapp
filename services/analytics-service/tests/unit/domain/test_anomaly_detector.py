from __future__ import annotations

from datetime import date, timedelta

from domain.services.anomaly_detector import evaluate_breach
from domain.value_objects.trend_point import TrendPoint

TODAY = date(2026, 6, 8)


def _points(values_by_days_ago: dict[int, float]) -> list[TrendPoint]:
    return [
        TrendPoint(on_date=TODAY - timedelta(days=n), value=v)
        for n, v in values_by_days_ago.items()
    ]


def test_exactly_five_of_seven_below_target_is_a_breach_inclusive_boundary():
    points = _points({0: 40, 1: 40, 2: 40, 3: 40, 4: 40, 5: 60, 6: 60})  # 5 below 50, 2 at/above
    result = evaluate_breach(points, target_min=50, lookback_days=7, threshold_days=5)

    assert result.breach is True
    assert result.insufficient_sample is False
    assert result.excluded_no_target is False
    assert result.sample_size == 7
    assert result.days_below_target == 5


def test_exactly_four_of_seven_below_target_is_not_a_breach():
    points = _points({0: 40, 1: 40, 2: 40, 3: 40, 4: 60, 5: 60, 6: 60})  # 4 below 50
    result = evaluate_breach(points, target_min=50, lookback_days=7, threshold_days=5)

    assert result.breach is False
    assert result.days_below_target == 4


def test_fewer_than_lookback_days_with_data_is_insufficient_sample_not_a_pass():
    points = _points({0: 10, 1: 10, 2: 10})  # only 3 days ever recorded, all deficient
    result = evaluate_breach(points, target_min=50, lookback_days=7, threshold_days=5)

    assert result.breach is False
    assert result.insufficient_sample is True
    assert result.sample_size == 3


def test_target_min_none_excludes_nutrient_from_evaluation():
    points = _points({0: 10, 1: 10, 2: 10, 3: 10, 4: 10, 5: 10, 6: 10})
    result = evaluate_breach(points, target_min=None)

    assert result.breach is False
    assert result.excluded_no_target is True
    assert result.insufficient_sample is False
    assert result.sample_size == 0


def test_large_n_two_independent_breach_windows_both_identified():
    # Most recent 7 days: 5 below target -> breach.
    recent_values = {0: 10, 1: 10, 2: 10, 3: 10, 4: 10, 5: 60, 6: 60}
    recent_points = _points(recent_values)
    recent_result = evaluate_breach(recent_points, target_min=50, lookback_days=7, threshold_days=5)
    assert recent_result.breach is True

    # An earlier, independent 7-day window (days 20-26 ago) also has 5 below target.
    earlier_points = [
        TrendPoint(on_date=TODAY - timedelta(days=n), value=v)
        for n, v in {20: 10, 21: 10, 22: 10, 23: 10, 24: 10, 25: 60, 26: 60}.items()
    ]
    earlier_result = evaluate_breach(
        earlier_points, target_min=50, lookback_days=7, threshold_days=5
    )
    assert earlier_result.breach is True
