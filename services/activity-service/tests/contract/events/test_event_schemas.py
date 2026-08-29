"""ExerciseLogged published payload matches
packages/shared-contracts/schemas/exercise_logged.v1.json (test-plan
section 3)."""

from __future__ import annotations

import json
import os

import jsonschema

from domain.events.exercise_logged import build_exercise_logged_event
from tests.fixtures.factories import make_exercise_entry

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


def _load_schema(name: str) -> dict:
    with open(os.path.join(SCHEMAS_DIR, name)) as f:
        return json.load(f)


def test_exercise_logged_payload_matches_schema():
    schema = _load_schema("exercise_logged.v1.json")
    entry = make_exercise_entry(duration_minutes=30, calories_burned_kcal=250.0)
    event = build_exercise_logged_event(entry=entry, correlation_id="c1")

    jsonschema.validate(instance=event.to_wire(), schema=schema)


def test_exercise_logged_payload_matches_schema_with_other_type_and_label():
    from domain.value_objects.exercise_type import ExerciseType

    entry = make_exercise_entry(exercise_type=ExerciseType.OTHER, label="frisbee")
    event = build_exercise_logged_event(entry=entry, correlation_id="c2")
    schema = _load_schema("exercise_logged.v1.json")

    jsonschema.validate(instance=event.to_wire(), schema=schema)
