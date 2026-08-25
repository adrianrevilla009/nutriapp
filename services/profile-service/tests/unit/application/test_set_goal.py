from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest

from application.commands.set_goal import SetGoalCommand, SetGoalHandler
from application.dto.event_crypto import encrypt_event_payload
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


async def _seed_profile(event_store, user_id):
    _profile, created = Profile.create(user_id, correlation_id="corr-0")
    await event_store.append(created)


async def test_valid_goal_passing_policy_persists_and_outboxes():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    snapshot = FakeSnapshotProjector()
    encryption = FakeDataEncryption()
    user_id = uuid.uuid4()
    await _seed_profile(event_store, user_id)

    handler = SetGoalHandler(event_store, outbox, snapshot, encryption, now_fn=_now)
    result = await handler.handle(
        SetGoalCommand(
            user_id=user_id,
            goal_type="LOSE",
            target_value=65.0,
            target_date=date(2026, 12, 1),
            correlation_id="corr-1",
        )
    )

    assert result.goal_type == "LOSE"
    assert len(outbox.enqueued) == 1
    assert outbox.enqueued[0].event_type == "GoalSet"


async def test_goal_failing_policy_rejected_before_any_repository_call():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    snapshot = FakeSnapshotProjector()
    encryption = FakeDataEncryption()
    user_id = uuid.uuid4()
    await _seed_profile(event_store, user_id)
    weight_profile = Profile.rebuild(await event_store.load(user_id))
    consent = weight_profile.grant_consent(_now(), correlation_id="corr-0b")
    await event_store.append(consent)
    weight_event = weight_profile.record_weight(WeightKg(70.0), _now(), correlation_id="corr-0c")
    encrypted_weight_event = await encrypt_event_payload(weight_event, encryption, user_id)
    await event_store.append(encrypted_weight_event)

    handler = SetGoalHandler(event_store, outbox, snapshot, encryption, now_fn=_now)
    with pytest.raises(InvalidGoalTargetError):
        await handler.handle(
            SetGoalCommand(
                user_id=user_id,
                goal_type="LOSE",
                target_value=90.0,  # not below latest weight (70.0) -- rejected
                target_date=date(2026, 12, 1),
                correlation_id="corr-1",
            )
        )

    assert outbox.enqueued == []
    assert (await event_store.load(user_id))[-1].event_type == "WeightRecorded"
