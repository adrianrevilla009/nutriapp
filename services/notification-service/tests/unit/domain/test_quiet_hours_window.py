"""QuietHoursWindow -- midnight-crossing window + ambiguous-window
rejection (test-plan section 1)."""

from __future__ import annotations

from datetime import datetime, time, timezone

import pytest

from domain.value_objects.quiet_hours_window import (
    AmbiguousQuietHoursWindowError,
    QuietHoursWindow,
)

_WINDOW = QuietHoursWindow(start=time(22, 0), end=time(8, 0), tz="UTC")


def test_same_start_and_end_raises():
    with pytest.raises(AmbiguousQuietHoursWindowError):
        QuietHoursWindow(start=time(9, 0), end=time(9, 0), tz="UTC")


def test_10_00_local_is_outside_quiet_hours():
    at = datetime(2026, 8, 28, 10, 0, tzinfo=timezone.utc)
    assert _WINDOW.contains(at) is False


def test_23_00_local_is_inside_quiet_hours():
    at = datetime(2026, 8, 28, 23, 0, tzinfo=timezone.utc)
    assert _WINDOW.contains(at) is True


def test_02_00_local_is_inside_quiet_hours_after_midnight():
    at = datetime(2026, 8, 28, 2, 0, tzinfo=timezone.utc)
    assert _WINDOW.contains(at) is True


def test_non_wrapping_window_works_normally():
    window = QuietHoursWindow(start=time(1, 0), end=time(5, 0), tz="UTC")
    assert window.contains(datetime(2026, 8, 28, 3, 0, tzinfo=timezone.utc)) is True
    assert window.contains(datetime(2026, 8, 28, 6, 0, tzinfo=timezone.utc)) is False
