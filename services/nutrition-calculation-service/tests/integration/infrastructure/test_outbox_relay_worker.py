from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.entities.daily_nutrition_total import DailyNutritionTotal
from domain.events.nutrition_value_recomputed import build_nutrition_value_recomputed_event
from domain.value_objects.formula_version import CURRENT_FORMULA_VERSION
from infrastructure.messaging.outbox_relay_worker import OutboxRelayWorker
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository

pytestmark = pytest.mark.usefixtures("db_engine")


class _FakePublisher:
    def __init__(self, fail: bool = False) -> None:
        self.published = []
        self.fail = fail

    async def publish(self, event) -> None:
        if self.fail:
            raise RuntimeError("publish failed")
        self.published.append(event)


def _event(user_id: uuid.UUID):
    line = DailyNutritionTotal(user_id=user_id, total_date=date(2026, 8, 25)).compute_total()
    return build_nutrition_value_recomputed_event(
        user_id=user_id,
        scope="day",
        entry_id=None,
        total_date=date(2026, 8, 25),
        line=line,
        confidence_range=None,
        formula_version=CURRENT_FORMULA_VERSION,
        reason="food_entry_logged",
        correlation_id="c1",
        recomputed_at=datetime.now(timezone.utc),
    )


async def test_outbox_row_inserted_in_same_transaction_is_relayed(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        outbox = PostgresOutboxRepository(session)
        event = _event(uuid.uuid4())
        await outbox.enqueue(event)
        await session.commit()

    publisher = _FakePublisher()
    worker = OutboxRelayWorker(session_factory, publisher)
    published_count = await worker.relay_once()

    assert published_count == 1
    assert publisher.published[0].event_type == "NutritionValueRecomputed"


async def test_publish_failure_leaves_row_unpublished_for_retry(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        outbox = PostgresOutboxRepository(session)
        event = _event(uuid.uuid4())
        await outbox.enqueue(event)
        await session.commit()

    failing_publisher = _FakePublisher(fail=True)
    worker = OutboxRelayWorker(session_factory, failing_publisher)
    with pytest.raises(RuntimeError):
        await worker.relay_once()

    async with session_factory() as session:
        outbox = PostgresOutboxRepository(session)
        pending = await outbox.fetch_unpublished()
    assert len(pending) == 1
