from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from application.commands.grant_biometric_consent import (
    GrantBiometricConsentCommand,
    GrantBiometricConsentHandler,
)
from application.errors import ProfileNotFoundError
from domain.entities.profile import Profile
from tests.fixtures.factories import FakeEventStore, FakeOutboxRepository, FakeSnapshotProjector

NOW = lambda: datetime(2026, 8, 24, tzinfo=timezone.utc)


async def _seed_profile(event_store, user_id):
    _profile, event = Profile.create(user_id, correlation_id="corr-0")
    await event_store.append(event)


async def test_first_grant_appends_and_outboxes_event():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    snapshot = FakeSnapshotProjector()
    user_id = uuid.uuid4()
    await _seed_profile(event_store, user_id)

    handler = GrantBiometricConsentHandler(event_store, outbox, snapshot, now_fn=NOW)
    result = await handler.handle(
        GrantBiometricConsentCommand(user_id=user_id, correlation_id="corr-1")
    )

    assert result.consent_granted is True
    assert len(outbox.enqueued) == 1
    assert outbox.enqueued[0].event_type == "BiometricConsentGranted"


async def test_second_grant_is_idempotent_no_duplicate_event():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    snapshot = FakeSnapshotProjector()
    user_id = uuid.uuid4()
    await _seed_profile(event_store, user_id)

    handler = GrantBiometricConsentHandler(event_store, outbox, snapshot, now_fn=NOW)
    await handler.handle(GrantBiometricConsentCommand(user_id=user_id, correlation_id="corr-1"))
    result = await handler.handle(
        GrantBiometricConsentCommand(user_id=user_id, correlation_id="corr-2")
    )

    assert result.consent_granted is True
    assert len(outbox.enqueued) == 1


async def test_grant_consent_for_unknown_profile_raises():
    handler = GrantBiometricConsentHandler(
        FakeEventStore(), FakeOutboxRepository(), FakeSnapshotProjector(), now_fn=NOW
    )
    command = GrantBiometricConsentCommand(user_id=uuid.uuid4(), correlation_id="corr-1")
    with pytest.raises(ProfileNotFoundError):
        await handler.handle(command)
