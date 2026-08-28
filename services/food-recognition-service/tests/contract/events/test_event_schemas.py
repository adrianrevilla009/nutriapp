"""FoodPhotoAnalyzed published payload matches
packages/shared-contracts/schemas/food_photo_analyzed.v1.json (test-plan
section 3), exercised for all three `status` values -- not just the happy
path."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

import jsonschema
import pytest

from domain.events.food_photo_analyzed import build_food_photo_analyzed_event
from tests.fixtures.factories import make_candidate

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


@pytest.mark.parametrize(
    ("status", "candidates"),
    [
        ("detected", [make_candidate(confidence=0.9)]),
        ("uncertain", [make_candidate(confidence=0.2)]),
        ("unavailable", []),
    ],
)
def test_food_photo_analyzed_payload_matches_schema(status, candidates):
    schema = _load_schema("food_photo_analyzed.v1.json")
    event = build_food_photo_analyzed_event(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        candidates=candidates,
        model_version="claude-haiku-4-5",
        status=status,
        correlation_id="corr-1",
        occurred_at=datetime.now(timezone.utc),
    )
    jsonschema.validate(instance=event.to_wire(), schema=schema)


def test_understanding_of_food_photo_analyzed_matches_shared_contracts():
    from shared_contracts.events.food_recognition import FoodPhotoAnalyzedPayloadV1

    payload = {
        "analysis_id": str(uuid.uuid4()),
        "candidates": [
            {
                "name": "apple",
                "portion_range_min_g": 100.0,
                "portion_range_max_g": 150.0,
                "confidence": 0.9,
            }
        ],
        "model_version": "claude-haiku-4-5",
        "status": "detected",
    }
    FoodPhotoAnalyzedPayloadV1.model_validate(payload)
