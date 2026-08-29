"""due_and_stale_policy -- test-plan section 1's three boundary cases."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from domain.services.due_and_stale_policy import ReminderEvaluation, evaluate

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


def test_due_at_past_relevance_future_is_due():
    result = evaluate(
        due_at=NOW - timedelta(hours=1), relevance_expires_at=NOW + timedelta(hours=1), now=NOW
    )
    assert result is ReminderEvaluation.DUE


def test_due_at_past_relevance_also_past_is_stale():
    result = evaluate(
        due_at=NOW - timedelta(hours=5), relevance_expires_at=NOW - timedelta(hours=1), now=NOW
    )
    assert result is ReminderEvaluation.STALE


def test_due_at_future_is_not_due():
    result = evaluate(
        due_at=NOW + timedelta(hours=1), relevance_expires_at=NOW + timedelta(hours=2), now=NOW
    )
    assert result is ReminderEvaluation.NOT_DUE
