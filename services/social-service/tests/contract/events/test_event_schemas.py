"""Both social-service events' published payloads match
packages/shared-contracts/schemas/*.json (test-plan section 3)."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

import jsonschema

from domain.events.user_followed import build_user_followed_event
from domain.events.user_unfollowed import build_user_unfollowed_event

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

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _load_schema(name: str) -> dict:
    with open(os.path.join(SCHEMAS_DIR, name)) as f:
        return json.load(f)


def test_user_followed_matches_schema():
    schema = _load_schema("user_followed.v1.json")
    event = build_user_followed_event(
        follow_id=uuid.uuid4(),
        follower_id=uuid.uuid4(),
        followee_id=uuid.uuid4(),
        followed_at=NOW,
        correlation_id="corr-1",
    )
    jsonschema.validate(instance=event.to_wire(), schema=schema)


def test_user_unfollowed_matches_schema():
    schema = _load_schema("user_unfollowed.v1.json")
    event = build_user_unfollowed_event(
        follow_id=uuid.uuid4(),
        follower_id=uuid.uuid4(),
        followee_id=uuid.uuid4(),
        unfollowed_at=NOW,
        correlation_id="corr-2",
    )
    jsonschema.validate(instance=event.to_wire(), schema=schema)
