from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest

from application.commands.set_goal import SetGoalCommand, SetGoalHandler
from application.commands.update_goal import UpdateGoalCommand, UpdateGoalHandler
from application.dto.event_crypto import decrypt_event_stream, encrypt_event_payload
from application.errors import ProfileNotFoundError
from domain.entities.profile import Profile
from domain.value_objects.goal_target import InvalidGoalTargetError
from domain.value_objects.weight_kg import WeightKg
from tests.fixtures.factories import (
    FakeDataEncryption,
    FakeEventStore,
    FakeOutboxRepository,
    FakeSnapshotProjector,
)


def _now():
    return datetime(2026, 8, 24, tzinfo=timezone.utc)


async def _seed_profile_with_goal(event_store, outbox, snapshot, encryption, user_id):
    _profile, created = Profile.create(user_id, correlation_id="corr-0")
    await event_store.append(created)
    set_handler = SetGoalHandler(event_store, outbox, snapshot, encryption, now_fn=_now)
    await set_handler.handle(
        SetGoalCommand(
            user_id=user_id,
            goal_type="LOSE",
            target_value=65.0,
            target_date=date(2026, 12, 1),
            correlation_id="corr-1",
        )
    )


async def test_update_goal_on_existing_goal_persists_and_outboxes():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    snapshot = FakeSnapshotProjector()
    encryption = FakeDataEncryption()
    user_id = uuid.uuid4()
    await _seed_profile_with_goal(event_store, outbox, snapshot, encryption, user_id)

    handler = UpdateGoalHandler(event_store, outbox, snapshot, encryption, now_fn=_now)
    result = await handler.handle(
        UpdateGoalCommand(
            user_id=user_id,
            goal_type="MAINTAIN",
            target_value=None,
            target_date=None,
            correlation_id="corr-2",
        )
    )

    assert result.goal_type == "MAINTAIN"
    assert result.previous_goal_type == "LOSE"
    assert len(outbox.enqueued) == 2  # GoalSet + GoalUpdated
    assert outbox.enqueued[-1].event_type == "GoalUpdated"


async def test_update_goal_failing_policy_rejected_before_any_repository_call():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    snapshot = FakeSnapshotProjector()
    encryption = FakeDataEncryption()
    user_id = uuid.uuid4()
    await _seed_profile_with_goal(event_store, outbox, snapshot, encryption, user_id)
    assert len(outbox.enqueued) == 1  # GoalSet only, so far

    plaintext_events = await decrypt_event_stream(
        await event_store.load(user_id), encryption, user_id
    )
    weight_profile = Profile.rebuild(plaintext_events)
    consent_event = weight_profile.grant_consent(_now(), correlation_id="corr-2z")
    await event_store.append(consent_event)
    weight_event = weight_profile.record_weight(WeightKg(70.0), _now(), correlation_id="corr-2a")
    encrypted_weight_event = await encrypt_event_payload(weight_event, encryption, user_id)
    await event_store.append(encrypted_weight_event)

    handler = UpdateGoalHandler(event_store, outbox, snapshot, encryption, now_fn=_now)
    with pytest.raises(InvalidGoalTargetError):
        await handler.handle(
            UpdateGoalCommand(
                user_id=user_id,
                goal_type="GAIN",
                target_value=65.0,  # not above latest weight (70.0) -- rejected for GAIN
                target_date=date(2026, 12, 1),
                correlation_id="corr-3",
            )
        )

    assert len(outbox.enqueued) == 1  # unchanged -- still just the seeded GoalSet
    assert (await event_store.load(user_id))[-1].event_type == "WeightRecorded"


async def test_update_goal_for_unknown_user_raises_profile_not_found_and_writes_nothing():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    snapshot = FakeSnapshotProjector()
    encryption = FakeDataEncryption()
    user_id = uuid.uuid4()  # never seeded -- empty event stream

    handler = UpdateGoalHandler(event_store, outbox, snapshot, encryption, now_fn=_now)
    with pytest.raises(ProfileNotFoundError):
        await handler.handle(
            UpdateGoalCommand(
                user_id=user_id,
                goal_type="MAINTAIN",
                target_value=None,
                target_date=None,
                correlation_id="corr-1",
            )
        )

    assert outbox.enqueued == []
    assert await event_store.load(user_id) == []
