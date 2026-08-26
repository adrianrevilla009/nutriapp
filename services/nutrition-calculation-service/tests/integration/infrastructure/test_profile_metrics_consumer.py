"""ProfileMetricsConsumer -- idempotency test (test-plan section 2): the
same WeightRecorded delivered twice triggers exactly one recompute,
asserted via a fake ProfileRevealPort call-count, not two."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from infrastructure.messaging.profile_metrics_consumer import ProfileMetricsConsumer
from infrastructure.persistence.postgres_nutrition_target_repository import (
    PostgresNutritionTargetRepository,
)
from tests.fixtures.factories import FakeProfileRevealPort

pytestmark = pytest.mark.usefixtures("db_engine")


def _weight_recorded_body(user_id: uuid.UUID, event_id: uuid.UUID | None = None) -> dict:
    return {
        "event_id": str(event_id or uuid.uuid4()),
        "aggregate_id": str(user_id),
        "event_type": "WeightRecorded",
        "version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "user_id": str(user_id),
            "weight_kg": "ciphertext-not-used-by-this-consumer",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        },
        "metadata": {"correlation_id": "corr-1", "causation_id": None, "user_id": str(user_id)},
    }


async def test_replayed_weight_recorded_calls_reveal_exactly_once(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    reveal_port = FakeProfileRevealPort()
    consumer = ProfileMetricsConsumer(session_factory, reveal_port)

    user_id = uuid.uuid4()
    event_id = uuid.uuid4()
    body = _weight_recorded_body(user_id, event_id=event_id)

    await consumer.process_body(body)
    await consumer.process_body(body)  # exact same event_id -- a redelivery

    assert reveal_port.call_count == 1

    async with session_factory() as session:
        repo = PostgresNutritionTargetRepository(session)
        target = await repo.get_current(user_id)
    assert target is not None


async def test_reveal_unavailable_defers_without_crashing(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    reveal_port = FakeProfileRevealPort(should_fail=True)
    consumer = ProfileMetricsConsumer(session_factory, reveal_port)

    user_id = uuid.uuid4()
    body = _weight_recorded_body(user_id)

    # Must not raise -- deferred cleanly, per implementation plan section 7.
    await consumer.process_body(body)

    async with session_factory() as session:
        repo = PostgresNutritionTargetRepository(session)
        target = await repo.get_current(user_id)
    assert target is None


async def test_non_recompute_event_type_is_ignored(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    reveal_port = FakeProfileRevealPort()
    consumer = ProfileMetricsConsumer(session_factory, reveal_port)

    body = _weight_recorded_body(uuid.uuid4())
    body["event_type"] = "ProfileCreated"

    await consumer.process_body(body)

    assert reveal_port.call_count == 0
