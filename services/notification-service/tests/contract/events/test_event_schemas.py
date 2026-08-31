"""Consumed-event payload contracts (test-plan section 3): each fixture
is validated against its docs/events-catalog.md schema, sourced from the
producing service's own published shared_contracts payload models --
never hand-guessed.

Exception: `UserFollowed` (social-service PR A, test-plan section 6) is
validated against the locally-defined `UserFollowedPayloadV1` in
`infrastructure/messaging/social_events_consumer.py`, not a
shared_contracts model -- social-service does not exist in this repository
yet (implementation-plan.md section 6's two-PR sequencing), so there is no
independently-published schema to source from. See that module's docstring
for the flagged follow-up once social-service exists for real."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from shared_contracts.events.diary import (
    FastingWindowEndedPayloadV1,
    FastingWindowStartedPayloadV1,
    MealPlannedPayloadV1,
    MealPlanRemovedPayloadV1,
    MealPlanUpdatedPayloadV1,
    WaterIntakeLoggedPayloadV1,
    WaterIntakeRemovedPayloadV1,
)
from shared_contracts.events.identity import (
    NewDeviceLoginDetectedPayloadV1,
    PasswordResetRequestedPayloadV1,
    UserRegisteredPayloadV1,
)

from infrastructure.messaging.social_events_consumer import UserFollowedPayloadV1

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"

_CASES = [
    ("identity_events/user_registered.json", "UserRegistered", UserRegisteredPayloadV1),
    (
        "identity_events/password_reset_requested.json",
        "PasswordResetRequested",
        PasswordResetRequestedPayloadV1,
    ),
    (
        "identity_events/new_device_login_detected.json",
        "NewDeviceLoginDetected",
        NewDeviceLoginDetectedPayloadV1,
    ),
    (
        "diary_events/fasting_window_started.json",
        "FastingWindowStarted",
        FastingWindowStartedPayloadV1,
    ),
    ("diary_events/fasting_window_ended.json", "FastingWindowEnded", FastingWindowEndedPayloadV1),
    ("diary_events/water_intake_logged.json", "WaterIntakeLogged", WaterIntakeLoggedPayloadV1),
    ("diary_events/water_intake_removed.json", "WaterIntakeRemoved", WaterIntakeRemovedPayloadV1),
    ("diary_events/meal_planned.json", "MealPlanned", MealPlannedPayloadV1),
    ("diary_events/meal_plan_updated.json", "MealPlanUpdated", MealPlanUpdatedPayloadV1),
    ("diary_events/meal_plan_removed.json", "MealPlanRemoved", MealPlanRemovedPayloadV1),
    ("social_events/user_followed.json", "UserFollowed", UserFollowedPayloadV1),
]


@pytest.mark.parametrize("fixture_path,expected_event_type,payload_model", _CASES)
def test_fixture_matches_producer_published_schema(
    fixture_path, expected_event_type, payload_model
):
    body = json.loads((FIXTURES_DIR / fixture_path).read_text())
    assert body["event_type"] == expected_event_type
    assert "event_id" in body
    assert "metadata" in body and "correlation_id" in body["metadata"]
    payload_model.model_validate(body["payload"])
