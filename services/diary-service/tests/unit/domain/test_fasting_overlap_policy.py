from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from domain.services.fasting_overlap_policy import WindowState, is_start_allowed

NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


def test_empty_window_list_is_always_accepted():
    assert is_start_allowed([]) is True


def test_exactly_one_open_window_is_always_rejected():
    windows = [WindowState(window_id=uuid.uuid4(), started_at=NOW, ended_at=None)]
    assert is_start_allowed(windows) is False


def test_only_closed_windows_any_count_is_accepted():
    windows = [
        WindowState(window_id=uuid.uuid4(), started_at=NOW - timedelta(days=i), ended_at=NOW)
        for i in range(5)
    ]
    assert is_start_allowed(windows) is True
