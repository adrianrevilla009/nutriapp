from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from domain.entities.meal_plan_entry import MealPlanEntry, PlanEntryAlreadyRemovedError
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


def _planned_entry():
    plan_entry_id = uuid.uuid4()
    user_id = uuid.uuid4()
    entry, event = MealPlanEntry.plan(
        plan_entry_id=plan_entry_id,
        user_id=user_id,
        source=_source(),
        meal_slot=MealSlot.DINNER,
        planned_for=NOW,
        correlation_id="corr-1",
    )
    return entry, event


def test_rebuild_from_planned_event_yields_planned_state():
    _entry, event = _planned_entry()
    rebuilt = MealPlanEntry.rebuild([event])
    assert rebuilt.meal_slot == MealSlot.DINNER
    assert rebuilt.source.snapshot.name == "Oats"


def test_update_produces_updated_event_original_retained_unmodified():
    entry, planned_event = _planned_entry()
    updated_event = entry.update(
        source=_source("Rice"),
        meal_slot=MealSlot.LUNCH,
        planned_for=NOW,
        updated_at=NOW,
        correlation_id="corr-2",
    )
    rebuilt = MealPlanEntry.rebuild([planned_event, updated_event])
    assert rebuilt.source.snapshot.name == "Rice"
    assert rebuilt.meal_slot == MealSlot.LUNCH
    assert planned_event.payload["source"]["snapshot"]["name"] == "Oats"


def test_remove_produces_removed_event():
    entry, planned_event = _planned_entry()
    removed_event = entry.remove(removed_at=NOW, correlation_id="corr-2")
    rebuilt = MealPlanEntry.rebuild([planned_event, removed_event])
    assert rebuilt.removed is True


def test_update_and_remove_after_removal_raise():
    entry, _planned_event = _planned_entry()
    entry.remove(removed_at=NOW, correlation_id="corr-2")
    with pytest.raises(PlanEntryAlreadyRemovedError):
        entry.remove(removed_at=NOW, correlation_id="corr-3")
    source = _source()
    with pytest.raises(PlanEntryAlreadyRemovedError):
        entry.update(
            source=source,
            meal_slot=MealSlot.LUNCH,
            planned_for=NOW,
            updated_at=NOW,
            correlation_id="corr-4",
        )
