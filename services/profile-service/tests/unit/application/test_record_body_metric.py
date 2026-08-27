from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from application.commands.record_body_metric import (
    RecordBodyMetricCommand,
    RecordBodyMetricHandler,
)
from domain.entities.profile import ConsentRequiredError, Profile
from tests.fixtures.factories import (
    FakeDataEncryption,
    FakeEventStore,
    FakeEvolutionProjector,
    FakeOutboxRepository,
    FakeSnapshotProjector,
)


def _now():
    return datetime(2026, 8, 24, tzinfo=timezone.utc)


async def _seed_profile(event_store, user_id, with_consent: bool):
    profile, created = Profile.create(user_id, correlation_id="corr-0")
    await event_store.append(created)
    if with_consent:
        consent = profile.grant_consent(_now(), correlation_id="corr-0b")
        await event_store.append(consent)


def _handler(event_store, outbox, snapshot, evolution, encryption):
    return RecordBodyMetricHandler(
        event_store, outbox, snapshot, evolution, encryption, now_fn=_now
    )


@pytest.mark.parametrize(
    "metric_type,value",
    [("height", 175.0), ("age", 30), ("sex", "MALE"), ("activity_level", "ACTIVE")],
)
async def test_consent_granted_records_each_metric_type(metric_type, value):
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    snapshot = FakeSnapshotProjector()
    evolution = FakeEvolutionProjector()
    encryption = FakeDataEncryption()
    user_id = uuid.uuid4()
    await _seed_profile(event_store, user_id, with_consent=True)

    handler = _handler(event_store, outbox, snapshot, evolution, encryption)
    result = await handler.handle(
        RecordBodyMetricCommand(
            user_id=user_id, metric_type=metric_type, value=value, correlation_id="corr-1"
        )
    )

    assert result.metric_type == metric_type
    assert len(outbox.enqueued) == 1
    assert len(evolution.entries) == 1


async def test_consent_not_granted_rejected_for_body_metric():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    snapshot = FakeSnapshotProjector()
    evolution = FakeEvolutionProjector()
    encryption = FakeDataEncryption()
    user_id = uuid.uuid4()
    await _seed_profile(event_store, user_id, with_consent=False)

    handler = _handler(event_store, outbox, snapshot, evolution, encryption)
    command = RecordBodyMetricCommand(
        user_id=user_id, metric_type="height", value=175.0, correlation_id="corr-1"
    )
    with pytest.raises(ConsentRequiredError):
        await handler.handle(command)
    assert outbox.enqueued == []
