"""Event schema contract tests: every published event's wire shape must
validate against packages/shared-contracts/schemas/*.json, the single
source of truth also referenced by docs/events-catalog.md.
"""
from __future__ import annotations

import json
import os
import uuid

import jsonschema
import pytest

from domain.events.new_device_login_detected import build_new_device_login_detected_event
from domain.events.password_reset_requested import build_password_reset_requested_event
from domain.events.user_registered import build_user_registered_event

SCHEMAS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "..", "packages", "shared-contracts", "schemas"
)


def load_schema(filename: str) -> dict:
    with open(os.path.join(SCHEMAS_DIR, filename)) as f:
        return json.load(f)


def test_user_registered__wire_shape__matches_shared_contracts_schema():
    event = build_user_registered_event(
        user_id=uuid.uuid4(),
        email="user@example.com",
        registered_at_iso="2026-01-01T00:00:00+00:00",
        email_verification_token_reference_id=uuid.uuid4(),
        correlation_id="corr-1",
    )
    jsonschema.validate(event.to_wire(), load_schema("user_registered.v1.json"))


def test_password_reset_requested__wire_shape__matches_shared_contracts_schema():
    event = build_password_reset_requested_event(
        user_id=uuid.uuid4(),
        email="user@example.com",
        reset_token_reference_id=uuid.uuid4(),
        requested_at_iso="2026-01-01T00:00:00+00:00",
        correlation_id="corr-1",
    )
    jsonschema.validate(event.to_wire(), load_schema("password_reset_requested.v1.json"))


def test_new_device_login_detected__wire_shape__matches_shared_contracts_schema():
    event = build_new_device_login_detected_event(
        user_id=uuid.uuid4(),
        device_fingerprint_hash="fp-hash",
        occurred_at_iso="2026-01-01T00:00:00+00:00",
        email="user@example.com",
        correlation_id="corr-1",
    )
    jsonschema.validate(event.to_wire(), load_schema("new_device_login_detected.v1.json"))


@pytest.mark.parametrize(
    "schema_file", ["user_registered.v1.json", "password_reset_requested.v1.json", "new_device_login_detected.v1.json"]
)
def test_schema_file__is_itself_valid_json_schema(schema_file):
    schema = load_schema(schema_file)
    jsonschema.Draft202012Validator.check_schema(schema)
