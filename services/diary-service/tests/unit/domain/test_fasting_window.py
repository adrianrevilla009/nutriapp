from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from domain.entities.fasting_window import (
    FastingWindow,
    OverlappingFastingWindowError,
    WindowAlreadyEndedError,
    WindowNotFoundError,
)

NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


def test_start_window_on_user_with_no_existing_windows_produces_started_event():
    user_id = uuid.uuid4()
    aggregate = FastingWindow.rebuild(user_id, [])
    event = aggregate.start_window(window_id=uuid.uuid4(), started_at=NOW, correlation_id="corr-1")
    assert event.event_type == "FastingWindowStarted"
    assert event.aggregate_id == str(user_id)


def test_start_window_while_open_window_exists_raises_no_event_produced():
    user_id = uuid.uuid4()
    aggregate = FastingWindow.rebuild(user_id, [])
    first_started = aggregate.start_window(uuid.uuid4(), NOW, "corr-1")

    rebuilt = FastingWindow.rebuild(user_id, [first_started])
    with pytest.raises(OverlappingFastingWindowError):
        rebuilt.start_window(uuid.uuid4(), NOW + timedelta(hours=1), "corr-2")
    # No new window was added as a side effect of the rejected attempt.
    assert len(rebuilt.windows) == 1


def test_start_window_after_previous_is_ended_succeeds():
    user_id = uuid.uuid4()
    aggregate = FastingWindow.rebuild(user_id, [])
    w1 = uuid.uuid4()
    started_1 = aggregate.start_window(w1, NOW, "corr-1")
    ended_1 = aggregate.end_window(w1, NOW + timedelta(hours=16), "corr-2")

    rebuilt = FastingWindow.rebuild(user_id, [started_1, ended_1])
    started_2 = rebuilt.start_window(uuid.uuid4(), NOW + timedelta(hours=20), "corr-3")
    assert started_2.event_type == "FastingWindowStarted"
    assert started_2.payload["window_id"] != str(w1)


def test_end_window_on_open_window_produces_ended_event():
    user_id = uuid.uuid4()
    aggregate = FastingWindow.rebuild(user_id, [])
    w1 = uuid.uuid4()
    started_1 = aggregate.start_window(w1, NOW, "corr-1")
    rebuilt = FastingWindow.rebuild(user_id, [started_1])
    ended = rebuilt.end_window(w1, NOW + timedelta(hours=16), "corr-2")
    assert ended.event_type == "FastingWindowEnded"


def test_end_window_on_already_ended_window_raises():
    user_id = uuid.uuid4()
    aggregate = FastingWindow.rebuild(user_id, [])
    w1 = uuid.uuid4()
    started_1 = aggregate.start_window(w1, NOW, "corr-1")
    ended_1 = aggregate.end_window(w1, NOW + timedelta(hours=16), "corr-2")
    rebuilt = FastingWindow.rebuild(user_id, [started_1, ended_1])
    with pytest.raises(WindowAlreadyEndedError):
        rebuilt.end_window(w1, NOW + timedelta(hours=20), "corr-3")


def test_end_window_for_unknown_window_id_raises():
    user_id = uuid.uuid4()
    aggregate = FastingWindow.rebuild(user_id, [])
    with pytest.raises(WindowNotFoundError):
        aggregate.end_window(uuid.uuid4(), NOW, "corr-1")


def test_full_replay_yields_one_open_and_one_closed_window():
    user_id = uuid.uuid4()
    aggregate = FastingWindow.rebuild(user_id, [])
    w1, w2 = uuid.uuid4(), uuid.uuid4()
    started_1 = aggregate.start_window(w1, NOW, "corr-1")
    ended_1 = aggregate.end_window(w1, NOW + timedelta(hours=16), "corr-2")
    rebuilt_for_w2 = FastingWindow.rebuild(user_id, [started_1, ended_1])
    started_2 = rebuilt_for_w2.start_window(w2, NOW + timedelta(hours=20), "corr-3")

    final = FastingWindow.rebuild(user_id, [started_1, ended_1, started_2])
    open_windows = [w for w in final.windows.values() if w.is_open]
    closed_windows = [w for w in final.windows.values() if not w.is_open]
    assert [w.window_id for w in open_windows] == [w2]
    assert [w.window_id for w in closed_windows] == [w1]
