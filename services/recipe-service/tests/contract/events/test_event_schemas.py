"""All four recipe-service events' published payloads match
packages/shared-contracts/schemas/*.json (test-plan section 3)."""

from __future__ import annotations

import json
import os
import uuid

import jsonschema

from domain.events.recipe_created import build_recipe_created_event
from domain.events.recipe_published import build_recipe_published_event
from domain.events.recipe_unpublished import build_recipe_unpublished_event
from domain.events.recipe_updated import build_recipe_updated_event

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


def test_recipe_created_matches_schema():
    schema = _load_schema("recipe_created.v1.json")
    event = build_recipe_created_event(
        recipe_id=uuid.uuid4(), user_id=uuid.uuid4(), correlation_id="corr-1"
    )
    jsonschema.validate(instance=event.to_wire(), schema=schema)


def test_recipe_updated_matches_schema():
    schema = _load_schema("recipe_updated.v1.json")
    event = build_recipe_updated_event(
        recipe_id=uuid.uuid4(), user_id=uuid.uuid4(), correlation_id="corr-2"
    )
    jsonschema.validate(instance=event.to_wire(), schema=schema)


def test_recipe_published_matches_schema():
    schema = _load_schema("recipe_published.v1.json")
    event = build_recipe_published_event(
        recipe_id=uuid.uuid4(), user_id=uuid.uuid4(), correlation_id="corr-3"
    )
    jsonschema.validate(instance=event.to_wire(), schema=schema)


def test_recipe_unpublished_matches_schema():
    schema = _load_schema("recipe_unpublished.v1.json")
    event = build_recipe_unpublished_event(
        recipe_id=uuid.uuid4(), user_id=uuid.uuid4(), correlation_id="corr-4"
    )
    jsonschema.validate(instance=event.to_wire(), schema=schema)
