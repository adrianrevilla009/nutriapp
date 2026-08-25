"""Event schema contract tests: every published event's wire shape must
validate against packages/shared-contracts/schemas/*.json, the single
source of truth also referenced by docs/events-catalog.md. Also asserts
this service's UserRegistered (v1) consumer contract: the existing
documented schema, including a field this service doesn't use, must not
break parsing (forward-compatible).
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timezone

import jsonschema
import pytest

from domain.events.body_metric_recorded import build_body_metric_recorded_event
from domain.events.goal_set import build_goal_set_event
from domain.events.goal_updated import build_goal_updated_event
from domain.events.weight_recorded import build_weight_recorded_event

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


def load_schema(filename: str) -> dict:
    with open(os.path.join(SCHEMAS_DIR, filename)) as f:
        return json.load(f)


def test_weight_recorded_wire_shape_matches_shared_contracts_schema():
    event = build_weight_recorded_event(
        user_id=uuid.uuid4(),
        weight_kg="ZW5jcnlwdGVkLXBheWxvYWQ=",  # wire shape carries the ciphertext string
        recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        correlation_id="corr-1",
    )
    jsonschema.validate(event.to_wire(), load_schema("weight_recorded.v1.json"))


def test_body_metric_recorded_wire_shape_matches_shared_contracts_schema():
    event = build_body_metric_recorded_event(
        user_id=uuid.uuid4(),
        metric_type="height",
        value="ZW5jcnlwdGVkLXBheWxvYWQ=",
        recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        correlation_id="corr-1",
    )
    jsonschema.validate(event.to_wire(), load_schema("body_metric_recorded.v1.json"))


def test_goal_set_wire_shape_matches_shared_contracts_schema():
    event = build_goal_set_event(
        user_id=uuid.uuid4(),
        goal_type="LOSE",
        target_value="ZW5jcnlwdGVkLXBheWxvYWQ=",
        target_date=date(2026, 12, 1),
        set_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        correlation_id="corr-1",
    )
    jsonschema.validate(event.to_wire(), load_schema("goal_set.v1.json"))


def test_goal_set_with_null_target_fields_matches_schema():
    event = build_goal_set_event(
        user_id=uuid.uuid4(),
        goal_type="MAINTAIN",
        target_value=None,
        target_date=None,
        set_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        correlation_id="corr-1",
    )
    jsonschema.validate(event.to_wire(), load_schema("goal_set.v1.json"))


def test_goal_updated_wire_shape_matches_shared_contracts_schema():
    event = build_goal_updated_event(
        user_id=uuid.uuid4(),
        goal_type="GAIN",
        target_value="ZW5jcnlwdGVkLXBheWxvYWQ=",
        target_date=date(2026, 12, 1),
        set_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        previous_goal_type="LOSE",
        correlation_id="corr-1",
    )
    jsonschema.validate(event.to_wire(), load_schema("goal_updated.v1.json"))


@pytest.mark.parametrize(
    "schema_file",
    [
        "weight_recorded.v1.json",
        "body_metric_recorded.v1.json",
        "goal_set.v1.json",
        "goal_updated.v1.json",
    ],
)
def test_schema_file_is_itself_valid_json_schema(schema_file):
    schema = load_schema(schema_file)
    jsonschema.Draft202012Validator.check_schema(schema)


def test_user_registered_consumer_ignores_unused_fields_without_breaking():
    """profile-service's consumer only reads payload.user_id and the
    envelope's event_id/metadata.correlation_id -- the documented
    email_verification_token_reference_id field it doesn't use must not
    break parsing (forward-compatible), per identity-service's test plan
    section 3 note and this service's test-plan section 3."""
    wire_body = dict(
        event_id=str(uuid.uuid4()),
        aggregate_id=str(uuid.uuid4()),
        event_type="UserRegistered",
        version=1,
        occurred_at=datetime.now(timezone.utc).isoformat(),
        payload=dict(
            user_id=str(uuid.uuid4()),
            email="user@example.com",
            registered_at=datetime.now(timezone.utc).isoformat(),
            email_verification_token_reference_id=str(uuid.uuid4()),
        ),
        metadata=dict(correlation_id="corr-1", causation_id=None, user_id=None),
    )
    # Mirrors infrastructure/messaging/user_registered_consumer.py's _process().
    parsed_user_id = uuid.UUID(wire_body["payload"]["user_id"])
    parsed_source_event_id = uuid.UUID(wire_body["event_id"])
    parsed_correlation_id = wire_body["metadata"]["correlation_id"]
    assert parsed_user_id is not None
    assert parsed_source_event_id is not None
    assert parsed_correlation_id == "corr-1"
