"""Validates the fixture payloads for all 8 events this service consumes
against their canonical schemas in packages/shared-contracts/schemas/
(test plan section 4). Mirrors analytics-service's own
test_consumed_event_fixtures.py precedent exactly."""

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

CONSUMED_EVENT_FIXTURES: list[tuple[str, str]] = [
    ("diary_events/food_entry_logged.json", "food_entry_logged.v1.json"),
    ("diary_events/food_entry_corrected.json", "food_entry_corrected.v1.json"),
    ("diary_events/food_entry_deleted.json", "food_entry_deleted.v1.json"),
    ("diary_events/water_intake_logged.json", "water_intake_logged.v1.json"),
    ("diary_events/water_intake_removed.json", "water_intake_removed.v1.json"),
    (
        "nutrition_calculation_events/nutrition_value_recomputed.json",
        "nutrition_value_recomputed.v1.json",
    ),
    (
        "nutrition_calculation_events/nutrition_target_updated.json",
        "nutrition_target_updated.v1.json",
    ),
    ("analytics_events/nutrient_deficiency_detected.json", "nutrient_deficiency_detected.v1.json"),
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


def test_dispatchers_can_parse_every_consumed_fixture():
    """Belt-and-suspenders: the fixture is not just schema-valid, this
    service's own dispatch functions can actually parse its payload
    without raising -- catches a case where the schema is satisfied but
    this service's own field-access assumptions are still wrong."""
    import asyncio
    import uuid

    from infrastructure.messaging.analytics_events_consumer import dispatch_analytics_event
    from infrastructure.messaging.diary_events_consumer import dispatch_diary_event
    from infrastructure.messaging.nutrition_calculation_events_consumer import (
        dispatch_nutrition_calculation_event,
    )

    class _NullSession:
        async def get(self, *a, **k):
            return None

        def add(self, *a, **k):
            pass

        async def flush(self, *a, **k):
            pass

        async def execute(self, *a, **k):
            class _R:
                def scalars(self):
                    class _S:
                        def all(self):
                            return []

                    return _S()

            return _R()

    async def _run():
        for fixture_relpath, _schema in CONSUMED_EVENT_FIXTURES:
            fixture = _load_json(FIXTURES_DIR, *fixture_relpath.split("/"))
            event_type = fixture["event_type"]
            event_id = uuid.UUID(fixture["event_id"])
            payload = fixture["payload"]
            session = _NullSession()
            if event_type in (
                "FoodEntryLogged",
                "FoodEntryCorrected",
                "FoodEntryDeleted",
                "WaterIntakeLogged",
                "WaterIntakeRemoved",
            ):
                await dispatch_diary_event(session, event_type, event_id, payload)  # type: ignore[arg-type]
            elif event_type in ("NutritionValueRecomputed", "NutritionTargetUpdated"):
                await dispatch_nutrition_calculation_event(session, event_type, event_id, payload)  # type: ignore[arg-type]
            elif event_type == "NutrientDeficiencyDetected":
                await dispatch_analytics_event(session, event_type, event_id, payload)  # type: ignore[arg-type]

    asyncio.run(_run())
