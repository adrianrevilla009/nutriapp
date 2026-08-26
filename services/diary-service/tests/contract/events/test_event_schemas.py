"""Event schema contract tests: every published event's wire shape must
validate against packages/shared-contracts/schemas/*.json, the single
source of truth also referenced by docs/events-catalog.md.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

import jsonschema
import pytest

from domain.events.fasting_window_ended import build_fasting_window_ended_event
from domain.events.fasting_window_started import build_fasting_window_started_event
from domain.events.food_entry_corrected import build_food_entry_corrected_event
from domain.events.food_entry_deleted import build_food_entry_deleted_event
from domain.events.food_entry_logged import build_food_entry_logged_event
from domain.events.meal_plan_removed import build_meal_plan_removed_event
from domain.events.meal_plan_updated import build_meal_plan_updated_event
from domain.events.meal_planned import build_meal_planned_event
from domain.events.water_intake_logged import build_water_intake_logged_event
from domain.events.water_intake_removed import build_water_intake_removed_event
from domain.value_objects.food_source import FoodSource, FoodSourceSnapshot
from domain.value_objects.macro_snapshot import MacroSnapshot
from domain.value_objects.meal_slot import MealSlot

SCHEMAS_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "..",
    "..",
    "packages",
    "shared-contracts",
    "schemas",
)

NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


def load_schema(filename: str) -> dict:
    with open(os.path.join(SCHEMAS_DIR, filename)) as f:
        return json.load(f)


def _source() -> FoodSource:
    return FoodSource(
        source_type="catalog_product",
        source_reference_id="prod-1",
        snapshot=FoodSourceSnapshot(
            name="Oats",
            brand=None,
            quantity=100.0,
            unit="g",
            macros_per_unit=MacroSnapshot(calories_kcal=100, protein_g=5, carbs_g=10, fat_g=2),
        ),
    )


def test_food_entry_logged_wire_shape_matches_schema():
    event = build_food_entry_logged_event(
        entry_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        source=_source(),
        meal_slot=MealSlot.BREAKFAST,
        occurred_at=NOW,
        correlation_id="corr-1",
    )
    jsonschema.validate(event.to_wire(), load_schema("food_entry_logged.v1.json"))


def test_food_entry_corrected_wire_shape_matches_schema():
    event = build_food_entry_corrected_event(
        entry_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        source=_source(),
        meal_slot=MealSlot.LUNCH,
        occurred_at=NOW,
        corrected_at=NOW,
        correlation_id="corr-1",
    )
    jsonschema.validate(event.to_wire(), load_schema("food_entry_corrected.v1.json"))


def test_food_entry_deleted_wire_shape_matches_schema():
    event = build_food_entry_deleted_event(
        entry_id=uuid.uuid4(), user_id=uuid.uuid4(), deleted_at=NOW, correlation_id="corr-1"
    )
    jsonschema.validate(event.to_wire(), load_schema("food_entry_deleted.v1.json"))


def test_water_intake_logged_wire_shape_matches_schema():
    event = build_water_intake_logged_event(
        intake_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        amount_ml=250.0,
        occurred_at=NOW,
        correlation_id="corr-1",
    )
    jsonschema.validate(event.to_wire(), load_schema("water_intake_logged.v1.json"))


def test_water_intake_removed_wire_shape_matches_schema():
    event = build_water_intake_removed_event(
        intake_id=uuid.uuid4(), user_id=uuid.uuid4(), removed_at=NOW, correlation_id="corr-1"
    )
    jsonschema.validate(event.to_wire(), load_schema("water_intake_removed.v1.json"))


def test_fasting_window_started_wire_shape_matches_schema():
    event = build_fasting_window_started_event(
        window_id=uuid.uuid4(), user_id=uuid.uuid4(), started_at=NOW, correlation_id="corr-1"
    )
    jsonschema.validate(event.to_wire(), load_schema("fasting_window_started.v1.json"))


def test_fasting_window_ended_wire_shape_matches_schema():
    event = build_fasting_window_ended_event(
        window_id=uuid.uuid4(), user_id=uuid.uuid4(), ended_at=NOW, correlation_id="corr-1"
    )
    jsonschema.validate(event.to_wire(), load_schema("fasting_window_ended.v1.json"))


def test_meal_planned_wire_shape_matches_schema():
    event = build_meal_planned_event(
        plan_entry_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        source=_source(),
        meal_slot=MealSlot.DINNER,
        planned_for=NOW,
        correlation_id="corr-1",
    )
    jsonschema.validate(event.to_wire(), load_schema("meal_planned.v1.json"))


def test_meal_plan_updated_wire_shape_matches_schema():
    event = build_meal_plan_updated_event(
        plan_entry_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        source=_source(),
        meal_slot=MealSlot.DINNER,
        planned_for=NOW,
        updated_at=NOW,
        correlation_id="corr-1",
    )
    jsonschema.validate(event.to_wire(), load_schema("meal_plan_updated.v1.json"))


def test_meal_plan_removed_wire_shape_matches_schema():
    event = build_meal_plan_removed_event(
        plan_entry_id=uuid.uuid4(), user_id=uuid.uuid4(), removed_at=NOW, correlation_id="corr-1"
    )
    jsonschema.validate(event.to_wire(), load_schema("meal_plan_removed.v1.json"))


@pytest.mark.parametrize(
    "schema_file",
    [
        "food_entry_logged.v1.json",
        "food_entry_corrected.v1.json",
        "food_entry_deleted.v1.json",
        "water_intake_logged.v1.json",
        "water_intake_removed.v1.json",
        "fasting_window_started.v1.json",
        "fasting_window_ended.v1.json",
        "meal_planned.v1.json",
        "meal_plan_updated.v1.json",
        "meal_plan_removed.v1.json",
    ],
)
def test_schema_file_is_itself_valid_json_schema(schema_file):
    schema = load_schema(schema_file)
    jsonschema.Draft202012Validator.check_schema(schema)
