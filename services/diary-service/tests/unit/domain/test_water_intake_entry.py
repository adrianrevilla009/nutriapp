from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from domain.entities.water_intake_entry import EntryAlreadyRemovedError, WaterIntakeEntry
from domain.value_objects.water_amount_ml import WaterAmountMl

NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


def _logged_entry():
    intake_id = uuid.uuid4()
    user_id = uuid.uuid4()
    entry, event = WaterIntakeEntry.log(
        intake_id=intake_id,
        user_id=user_id,
        amount=WaterAmountMl(250.0),
        occurred_at=NOW,
        correlation_id="corr-1",
    )
    return entry, event


def test_rebuild_from_logged_event_yields_logged_amount():
    _entry, event = _logged_entry()
    rebuilt = WaterIntakeEntry.rebuild([event])
    assert rebuilt.amount_ml == 250.0
    assert rebuilt.removed is False


def test_remove_produces_removed_event_and_rebuild_yields_removed_true():
    entry, event = _logged_entry()
    removed_event = entry.remove(removed_at=NOW, correlation_id="corr-2")
    rebuilt = WaterIntakeEntry.rebuild([event, removed_event])
    assert rebuilt.removed is True


def test_remove_called_twice_raises():
    entry, _event = _logged_entry()
    entry.remove(removed_at=NOW, correlation_id="corr-2")
    with pytest.raises(EntryAlreadyRemovedError):
        entry.remove(removed_at=NOW, correlation_id="corr-3")
