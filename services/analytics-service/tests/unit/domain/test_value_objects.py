from __future__ import annotations

from datetime import date

import pytest

from domain.value_objects.deficiency_signal import DeficiencySignal, InvalidDeficiencySignalError
from domain.value_objects.macro_running_total import (
    InvalidMacroRunningTotalError,
    MacroRunningTotal,
)
from domain.value_objects.report_period import InvalidReportPeriodError, ReportPeriod
from domain.value_objects.streak_summary import InvalidStreakSummaryError, StreakSummary


def test_streak_summary_rejects_negative_sample_size():
    with pytest.raises(InvalidStreakSummaryError):
        StreakSummary(current_streak_days=0, sample_size=-1, window_days=7)


def test_streak_summary_rejects_non_positive_window_days():
    with pytest.raises(InvalidStreakSummaryError):
        StreakSummary(current_streak_days=0, sample_size=0, window_days=0)


def test_streak_summary_valid_construction():
    summary = StreakSummary(current_streak_days=3, sample_size=5, window_days=7)
    assert summary.current_streak_days == 3


def test_macro_running_total_rejects_negative_sample_size():
    with pytest.raises(InvalidMacroRunningTotalError):
        MacroRunningTotal(
            sample_size=-1,
            window_days=7,
            avg_calories_kcal=None,
            avg_protein_g=None,
            avg_carbs_g=None,
            avg_fat_g=None,
            avg_water_ml=None,
        )


def test_macro_running_total_rejects_non_positive_window_days():
    with pytest.raises(InvalidMacroRunningTotalError):
        MacroRunningTotal(
            sample_size=0,
            window_days=0,
            avg_calories_kcal=None,
            avg_protein_g=None,
            avg_carbs_g=None,
            avg_fat_g=None,
            avg_water_ml=None,
        )


def test_macro_running_total_zero_sample_size_must_never_carry_an_average():
    with pytest.raises(InvalidMacroRunningTotalError):
        MacroRunningTotal(
            sample_size=0,
            window_days=7,
            avg_calories_kcal=0.0,
            avg_protein_g=None,
            avg_carbs_g=None,
            avg_fat_g=None,
            avg_water_ml=None,
        )


def test_deficiency_signal_requires_non_empty_nutrient():
    with pytest.raises(InvalidDeficiencySignalError):
        DeficiencySignal(nutrient="", value=10, target_min=50, window_days=7, sample_size=7)


def test_deficiency_signal_requires_non_empty_disclaimer():
    with pytest.raises(InvalidDeficiencySignalError):
        DeficiencySignal(
            nutrient="protein_g",
            value=10,
            target_min=50,
            window_days=7,
            sample_size=7,
            disclaimer="   ",
        )


def test_deficiency_signal_default_disclaimer_present_and_non_diagnostic():
    signal = DeficiencySignal(
        nutrient="protein_g", value=10, target_min=50, window_days=7, sample_size=7
    )
    assert "not a medical diagnosis" in signal.disclaimer
    assert "consult" in signal.disclaimer.lower()


def test_report_period_rejects_start_after_end():
    with pytest.raises(InvalidReportPeriodError):
        ReportPeriod(start_date=date(2026, 6, 8), end_date=date(2026, 6, 1), row_count=0)


def test_report_period_rejects_negative_row_count():
    with pytest.raises(InvalidReportPeriodError):
        ReportPeriod(start_date=date(2026, 6, 1), end_date=date(2026, 6, 8), row_count=-1)


def test_report_period_window_days_inclusive():
    period = ReportPeriod(start_date=date(2026, 6, 1), end_date=date(2026, 6, 8), row_count=10)
    assert period.window_days == 8
