"""`NutrientDeficiencyDetected`'s published payload matches
packages/shared-contracts/schemas/nutrient_deficiency_detected.v1.json
(test-plan section 4)."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

import jsonschema

from domain.events.nutrient_deficiency_detected import build_nutrient_deficiency_detected_event
from domain.value_objects.deficiency_signal import DeficiencySignal

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

NOW = datetime(2026, 6, 8, tzinfo=timezone.utc)


def _load_schema(name: str) -> dict:
    with open(os.path.join(SCHEMAS_DIR, name)) as f:
        return json.load(f)


def test_nutrient_deficiency_detected_matches_schema():
    schema = _load_schema("nutrient_deficiency_detected.v1.json")
    signal = DeficiencySignal(
        nutrient="protein_g", value=30.0, target_min=50.0, window_days=7, sample_size=7
    )
    event = build_nutrient_deficiency_detected_event(
        user_id=uuid.uuid4(), signal=signal, detected_at=NOW, correlation_id="corr-1"
    )
    jsonschema.validate(instance=event.to_wire(), schema=schema)
