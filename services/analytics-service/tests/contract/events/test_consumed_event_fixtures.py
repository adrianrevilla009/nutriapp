"""Validates the fixture payloads for all 9 events this service consumes
against their canonical schemas in packages/shared-contracts/schemas/
(test-plan section 4 / section 8's fixture requirement, both previously
missing -- flagged by qa-agent's test review).

This is deliberately separate from `test_event_schemas.py` (which covers
the ONE event this service publishes, `NutrientDeficiencyDetected`,
built from this service's own domain builder function) -- these fixtures
instead stand in for the real upstream producers' output, so a real
upstream schema change (e.g. diary-service adding/removing a required
field) would fail this test the next time these fixture files are
refreshed against the schema, catching drift that the consumer
integration tests' hand-constructed inline JSON bodies would not."""

from __future__ import annotations

import json
import os

import jsonschema
import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures")
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

# (fixture relative path, schema file name) -- covers all 9 consumed
# events across the four upstream producers this service subscribes to.
CONSUMED_EVENT_FIXTURES: list[tuple[str, str]] = [
    ("diary_events/food_entry_logged.json", "food_entry_logged.v1.json"),
    ("diary_events/food_entry_corrected.json", "food_entry_corrected.v1.json"),
    ("diary_events/food_entry_deleted.json", "food_entry_deleted.v1.json"),
    ("diary_events/water_intake_logged.json", "water_intake_logged.v1.json"),
    ("diary_events/water_intake_removed.json", "water_intake_removed.v1.json"),
    ("profile_events/weight_recorded.json", "weight_recorded.v1.json"),
    (
        "nutrition_calculation_events/nutrition_value_recomputed.json",
        "nutrition_value_recomputed.v1.json",
    ),
    (
        "nutrition_calculation_events/nutrition_target_updated.json",
        "nutrition_target_updated.v1.json",
    ),
    ("billing_responses/entitlement_granted.json", "entitlement_granted.v1.json"),
    ("billing_responses/entitlement_revoked.json", "entitlement_revoked.v1.json"),
]


def _load_json(*path_parts: str) -> dict:
    with open(os.path.join(*path_parts)) as f:
        return json.load(f)


@pytest.mark.parametrize(
    "fixture_relpath,schema_name",
    CONSUMED_EVENT_FIXTURES,
    ids=[schema for _fixture, schema in CONSUMED_EVENT_FIXTURES],
)
def test_consumed_event_fixture_matches_canonical_schema(fixture_relpath: str, schema_name: str):
    fixture = _load_json(FIXTURES_DIR, *fixture_relpath.split("/"))
    schema = _load_json(SCHEMAS_DIR, schema_name)

    jsonschema.validate(instance=fixture, schema=schema)
