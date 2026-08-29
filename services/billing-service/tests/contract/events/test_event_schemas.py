"""All six billing events' published payloads match
packages/shared-contracts/schemas/*.json (test-plan section 3)."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import jsonschema

from domain.events.entitlement_granted import build_entitlement_granted_event
from domain.events.entitlement_revoked import build_entitlement_revoked_event
from domain.events.subscription_cancelled import build_subscription_cancelled_event
from domain.events.subscription_payment_failed import build_subscription_payment_failed_event
from domain.events.subscription_renewed import build_subscription_renewed_event
from domain.events.subscription_started import build_subscription_started_event
from tests.fixtures.factories import make_subscription

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


def test_subscription_started_matches_schema():
    schema = _load_schema("subscription_started.v1.json")
    sub = make_subscription()
    event = build_subscription_started_event(subscription=sub, correlation_id="corr-1")
    jsonschema.validate(instance=event.to_wire(), schema=schema)


def test_subscription_renewed_matches_schema():
    schema = _load_schema("subscription_renewed.v1.json")
    sub = make_subscription()
    renewed = sub.renew(current_period_end=NOW + timedelta(days=30), now=NOW)
    event = build_subscription_renewed_event(subscription=renewed, correlation_id="corr-2")
    jsonschema.validate(instance=event.to_wire(), schema=schema)


def test_subscription_cancelled_matches_schema():
    schema = _load_schema("subscription_cancelled.v1.json")
    sub = make_subscription()
    cancelled = sub.cancel(NOW)
    event = build_subscription_cancelled_event(subscription=cancelled, correlation_id="corr-3")
    jsonschema.validate(instance=event.to_wire(), schema=schema)


def test_subscription_payment_failed_matches_schema():
    schema = _load_schema("subscription_payment_failed.v1.json")
    sub = make_subscription()
    past_due = sub.mark_past_due(NOW)
    event = build_subscription_payment_failed_event(subscription=past_due, correlation_id="corr-4")
    jsonschema.validate(instance=event.to_wire(), schema=schema)


def test_entitlement_granted_matches_schema():
    schema = _load_schema("entitlement_granted.v1.json")
    event = build_entitlement_granted_event(user_id=uuid.uuid4(), correlation_id="corr-5")
    jsonschema.validate(instance=event.to_wire(), schema=schema)


def test_entitlement_revoked_matches_schema():
    schema = _load_schema("entitlement_revoked.v1.json")
    event = build_entitlement_revoked_event(user_id=uuid.uuid4(), correlation_id="corr-6")
    jsonschema.validate(instance=event.to_wire(), schema=schema)
