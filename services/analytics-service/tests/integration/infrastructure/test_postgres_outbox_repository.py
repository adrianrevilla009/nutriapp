"""Postgres-backed outbox round trip -- enqueue/fetch_unpublished/
mark_published against a real DB (test-plan section 3)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domain.events.base import DomainEvent, EventMetadata
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository


def _event() -> DomainEvent:
    import uuid

    return DomainEvent(
        aggregate_id=str(uuid.uuid4()),
        event_type="NutrientDeficiencyDetected",
        version=1,
        payload={"user_id": str(uuid.uuid4())},
        metadata=EventMetadata(correlation_id="corr-1"),
    )


async def test_enqueue_fetch_and_mark_published(db_engine):
    event = _event()

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresOutboxRepository(session)
        await repo.enqueue(event)
        await session.commit()

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresOutboxRepository(session)
        pending = await repo.fetch_unpublished()
        assert any(e.event_id == event.event_id for e in pending)

        await repo.mark_published(event.event_id)
        await session.commit()

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresOutboxRepository(session)
        pending_after = await repo.fetch_unpublished()
        assert not any(e.event_id == event.event_id for e in pending_after)
