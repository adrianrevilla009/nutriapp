"""Mandatory projector-replay test for the evolution timeline read model:
same fixed sequence produces the expected ordered profile_evolution rows,
correction events appended as extra rows (never overwritten)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.profile import Profile
from domain.value_objects.weight_kg import WeightKg
from infrastructure.persistence.postgres_evolution_projector import PostgresEvolutionProjector


@pytest.fixture
async def session(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as s:
        yield s


async def test_replaying_fixed_event_sequence_produces_expected_evolution_rows(session):
    now = datetime(2026, 8, 24, tzinfo=timezone.utc)
    user_id = uuid.uuid4()
    profile, created = Profile.create(user_id, correlation_id="corr-0")
    consent = profile.grant_consent(now, correlation_id="corr-1")
    first_weight = profile.record_weight(WeightKg(70.0), now, correlation_id="corr-2")
    second_weight = profile.record_weight(
        WeightKg(68.0), now, correlation_id="corr-3"
    )  # correction
    height = profile.record_body_metric("height", 175.0, now, correlation_id="corr-4")

    projector = PostgresEvolutionProjector(session)
    for event in [created, consent, first_weight, second_weight, height]:
        await projector.apply(event)
    await session.commit()

    weight_rows = await projector.get_evolution(user_id, "weight_kg", None, None)
    assert [r["value"] for r in weight_rows] == [
        "70.0",
        "68.0",
    ]  # both retained, correction appended

    height_rows = await projector.get_evolution(user_id, "height", None, None)
    assert [r["value"] for r in height_rows] == ["175.0"]

    # ProfileCreated/BiometricConsentGranted are not metrics -- no rows.
    unknown_metric_rows = await projector.get_evolution(user_id, "does_not_exist", None, None)
    assert unknown_metric_rows == []


async def test_replaying_the_same_event_sequence_twice_does_not_duplicate_rows(session):
    """Read models must be disposable/rebuildable by replaying events
    (cqrs-event-sourcing SKILL.md) -- replaying the same event a second
    time (redelivery, or a replay run twice without truncating first) must
    be a no-op, not a duplicate row or an IntegrityError."""
    now = datetime(2026, 8, 24, tzinfo=timezone.utc)
    user_id = uuid.uuid4()
    profile, created = Profile.create(user_id, correlation_id="corr-0")
    consent = profile.grant_consent(now, correlation_id="corr-1")
    weight = profile.record_weight(WeightKg(70.0), now, correlation_id="corr-2")
    events = [created, consent, weight]

    projector = PostgresEvolutionProjector(session)
    for event in events:
        await projector.apply(event)
    await session.commit()

    # Replay the exact same event stream a second time (simulating either
    # redelivery of an already-applied event, or a rebuild run twice).
    for event in events:
        await projector.apply(event)
    await session.commit()

    weight_rows = await projector.get_evolution(user_id, "weight_kg", None, None)
    assert [r["value"] for r in weight_rows] == ["70.0"]  # still exactly one row
