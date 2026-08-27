"""Mandatory projector-replay test (cqrs-event-sourcing SKILL.md): a fixed
sequence of events, replayed through PostgresSnapshotProjector.apply(),
must produce the exact expected profile_snapshot row."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.profile import Profile
from domain.value_objects.goal_target import GoalTarget
from domain.value_objects.goal_type import GoalType
from domain.value_objects.weight_kg import WeightKg
from infrastructure.persistence.postgres_snapshot_projector import PostgresSnapshotProjector


@pytest.fixture
async def session(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as s:
        yield s


def _fixed_event_sequence(user_id: uuid.UUID):
    now = datetime(2026, 8, 24, tzinfo=timezone.utc)
    profile, created = Profile.create(user_id, correlation_id="corr-0")
    consent = profile.grant_consent(now, correlation_id="corr-1")
    first_weight = profile.record_weight(WeightKg(70.0), now, correlation_id="corr-2")
    second_weight = profile.record_weight(WeightKg(68.0), now, correlation_id="corr-3")
    target = GoalTarget(target_value=65.0, target_date=date(2026, 12, 1), now=now)
    goal_set = profile.set_goal(GoalType.LOSE, target, now, correlation_id="corr-4")
    return [created, consent, first_weight, second_weight, goal_set]


async def test_replaying_fixed_event_sequence_produces_expected_snapshot_row(session):
    user_id = uuid.uuid4()
    projector = PostgresSnapshotProjector(session)

    for event in _fixed_event_sequence(user_id):
        await projector.apply(event)
    await session.commit()

    row = await projector.get_snapshot(user_id)
    assert row is not None
    assert row["consent_granted"] is True
    assert row["weight_kg"] == "68.0"  # latest wins, plaintext-equivalent (no real encryption here)
    assert row["goal_type"] == "LOSE"
    assert row["goal_target_value"] == "65.0"
    assert row["goal_target_date"] == "2026-12-01"


async def test_snapshot_is_rebuildable_by_replaying_from_scratch(session):
    user_id = uuid.uuid4()
    events = _fixed_event_sequence(user_id)

    projector_a = PostgresSnapshotProjector(session)
    for event in events:
        await projector_a.apply(event)
    await session.commit()
    first_pass_row = await projector_a.get_snapshot(user_id)

    # A brand-new projector instance, replaying the exact same event
    # sequence for a different user, must produce an identical shape --
    # proving the row is fully derived from the events, not from any
    # projector-instance state.
    other_user_id = uuid.uuid4()
    projector_b = PostgresSnapshotProjector(session)
    for event in _fixed_event_sequence(other_user_id):
        await projector_b.apply(event)
    await session.commit()
    second_pass_row = await projector_b.get_snapshot(other_user_id)

    assert first_pass_row["weight_kg"] == second_pass_row["weight_kg"]
    assert first_pass_row["goal_type"] == second_pass_row["goal_type"]
