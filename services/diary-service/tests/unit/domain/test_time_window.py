from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from domain.value_objects.time_window import InvalidTimeWindowError, TimeWindow

NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


def test_end_before_start_raises():
    with pytest.raises(InvalidTimeWindowError):
        TimeWindow(start=NOW, end=NOW - timedelta(hours=1))


def test_end_absent_is_valid_open_state():
    window = TimeWindow(start=NOW)
    assert window.is_open is True
