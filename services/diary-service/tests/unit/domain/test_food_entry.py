from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from domain.entities.food_entry import EntryAlreadyDeletedError, FoodEntry
from domain.value_objects.food_source import FoodSource, FoodSourceSnapshot
from domain.value_objects.macro_snapshot import MacroSnapshot
from domain.value_objects.meal_slot import MealSlot

NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


def _source(name: str = "Oats") -> FoodSource:
    return FoodSource(
        source_type="catalog_product",
        source_reference_id="prod-1",
        snapshot=FoodSourceSnapshot(
            name=name,
            brand=None,
            quantity=100.0,
            unit="g",
            macros_per_unit=MacroSnapshot(calories_kcal=100, protein_g=5, carbs_g=10, fat_g=2),
        ),
    )


def _logged_entry():
    entry_id = uuid.uuid4()
    user_id = uuid.uuid4()
    entry, event = FoodEntry.log(
        entry_id=entry_id,
        user_id=user_id,
        source=_source(),
        meal_slot=MealSlot.BREAKFAST,
        occurred_at=NOW,
        correlation_id="corr-1",
    )
    return entry, event, entry_id, user_id


def test_rebuild_from_logged_event_yields_logged_state():
    _entry, event, entry_id, _user_id = _logged_entry()
    rebuilt = FoodEntry.rebuild([event])
    assert rebuilt.entry_id == entry_id
    assert rebuilt.meal_slot == MealSlot.BREAKFAST
    assert rebuilt.source.snapshot.name == "Oats"
    assert rebuilt.deleted is False


def test_correct_produces_corrected_event_and_rebuild_yields_corrected_values():
    entry, logged_event, _entry_id, _user_id = _logged_entry()
    corrected_event = entry.correct(
        source=_source("Steel-Cut Oats"),
        meal_slot=MealSlot.LUNCH,
        occurred_at=NOW,
        corrected_at=NOW,
        correlation_id="corr-2",
    )
    assert corrected_event.event_type == "FoodEntryCorrected"

    rebuilt = FoodEntry.rebuild([logged_event, corrected_event])
    assert rebuilt.source.snapshot.name == "Steel-Cut Oats"
    assert rebuilt.meal_slot == MealSlot.LUNCH
    # Original event is retained, unmodified, in the replayed stream.
    assert logged_event.payload["source"]["snapshot"]["name"] == "Oats"


def test_second_correction_wins_all_corrections_retained_in_history():
    entry, logged_event, _entry_id, _user_id = _logged_entry()
    first_correction = entry.correct(
        source=_source("Steel-Cut Oats"),
        meal_slot=MealSlot.LUNCH,
        occurred_at=NOW,
        corrected_at=NOW,
        correlation_id="corr-2",
    )
    second_correction = entry.correct(
        source=_source("Rolled Oats"),
        meal_slot=MealSlot.DINNER,
        occurred_at=NOW,
        corrected_at=NOW,
        correlation_id="corr-3",
    )
    stream = [logged_event, first_correction, second_correction]
    rebuilt = FoodEntry.rebuild(stream)
    assert rebuilt.source.snapshot.name == "Rolled Oats"
    assert rebuilt.meal_slot == MealSlot.DINNER
    assert len(stream) == 3  # all corrections retained in history


def test_delete_produces_deleted_event_and_rebuild_yields_deleted_true():
    entry, logged_event, _entry_id, _user_id = _logged_entry()
    deleted_event = entry.delete(deleted_at=NOW, correlation_id="corr-2")
    rebuilt = FoodEntry.rebuild([logged_event, deleted_event])
    assert rebuilt.deleted is True


def test_correct_after_deletion_raises():
    entry, _logged_event, _entry_id, _user_id = _logged_entry()
    entry.delete(deleted_at=NOW, correlation_id="corr-2")
    with pytest.raises(EntryAlreadyDeletedError):
        entry.correct(
            source=_source(),
            meal_slot=MealSlot.LUNCH,
            occurred_at=NOW,
            corrected_at=NOW,
            correlation_id="corr-3",
        )
