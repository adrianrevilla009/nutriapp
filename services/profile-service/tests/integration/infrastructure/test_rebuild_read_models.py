"""scripts/rebuild_read_models.py: replaying profile_events from scratch
must reproduce both read models exactly, proving the CQRS "read models are
disposable/rebuildable by replaying events" invariant is an actual runnable
capability, not just a docstring assertion (cqrs-event-sourcing SKILL.md)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.profile import Profile
from domain.value_objects.weight_kg import WeightKg
from infrastructure.persistence.postgres_event_store import PostgresEventStore
from infrastructure.persistence.postgres_evolution_projector import PostgresEvolutionProjector
from infrastructure.persistence.postgres_snapshot_projector import PostgresSnapshotProjector
from scripts.rebuild_read_models import rebuild_read_models


@pytest.fixture()
async def session(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as s:
        yield s


async def _seed_events(session: AsyncSession, user_id: uuid.UUID) -> None:
    now = datetime(2026, 8, 24, tzinfo=timezone.utc)
    event_store = PostgresEventStore(session)
    profile, created = Profile.create(user_id, correlation_id="corr-0")
    await event_store.append(created)
    consent = profile.grant_consent(now, correlation_id="corr-1")
    await event_store.append(consent)
    weight = profile.record_weight(WeightKg(70.0), now, correlation_id="corr-2")
    await event_store.append(weight)
    correction = profile.record_weight(WeightKg(68.0), now, correlation_id="corr-3")
    await event_store.append(correction)
    await session.commit()


async def test_rebuild_replays_events_and_reproduces_both_read_models(session):
    user_id = uuid.uuid4()
    await _seed_events(session, user_id)

    replayed = await rebuild_read_models(session)
    assert replayed == 4

    snapshot_projector = PostgresSnapshotProjector(session)
    snapshot = await snapshot_projector.get_snapshot(user_id)
    assert snapshot is not None
    assert snapshot["consent_granted"] is True
    assert snapshot["weight_kg"] == "68.0"  # latest value wins

    evolution_projector = PostgresEvolutionProjector(session)
    evolution_rows = await evolution_projector.get_evolution(user_id, "weight_kg", None, None)
    assert [r["value"] for r in evolution_rows] == ["70.0", "68.0"]  # both retained


async def test_rebuild_run_twice_is_idempotent_no_duplicate_rows(session):
    user_id = uuid.uuid4()
    await _seed_events(session, user_id)

    await rebuild_read_models(session)
    replayed_second_run = await rebuild_read_models(session)
    assert replayed_second_run == 4  # truncates first, so it re-replays everything again

    evolution_projector = PostgresEvolutionProjector(session)
    evolution_rows = await evolution_projector.get_evolution(user_id, "weight_kg", None, None)
    assert [r["value"] for r in evolution_rows] == ["70.0", "68.0"]  # still exactly two rows
