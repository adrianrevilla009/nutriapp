from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from application.commands.record_weight import RecordWeightCommand, RecordWeightHandler
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
    return RecordWeightHandler(event_store, outbox, snapshot, evolution, encryption, now_fn=_now)


async def test_consent_granted_records_weight_encrypted_before_persistence():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    snapshot = FakeSnapshotProjector()
    evolution = FakeEvolutionProjector()
    encryption = FakeDataEncryption()
    user_id = uuid.uuid4()
    await _seed_profile(event_store, user_id, with_consent=True)

    handler = _handler(event_store, outbox, snapshot, evolution, encryption)
    result = await handler.handle(
        RecordWeightCommand(user_id=user_id, weight_kg=70.0, correlation_id="corr-1")
    )

    assert result.weight_kg == 70.0
    assert len(encryption.encrypt_calls) == 1
    assert encryption.encrypt_calls[0] == (user_id, "70.0")
    assert len(outbox.enqueued) == 1
    stored_events = await event_store.load(user_id)
    weight_event = stored_events[-1]
    assert weight_event.payload["weight_kg"] != 70.0  # stored value is ciphertext, not plaintext
    assert snapshot.rows[user_id]["weight_kg"] is not None
    assert len(evolution.entries) == 1


async def test_consent_not_granted_rejected_nothing_persisted():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    snapshot = FakeSnapshotProjector()
    evolution = FakeEvolutionProjector()
    encryption = FakeDataEncryption()
    user_id = uuid.uuid4()
    await _seed_profile(event_store, user_id, with_consent=False)

    handler = _handler(event_store, outbox, snapshot, evolution, encryption)
    with pytest.raises(ConsentRequiredError):
        await handler.handle(
            RecordWeightCommand(user_id=user_id, weight_kg=70.0, correlation_id="corr-1")
        )

    assert outbox.enqueued == []
    assert evolution.entries == []
