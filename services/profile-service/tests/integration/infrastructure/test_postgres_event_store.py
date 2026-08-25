from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domain.events.base import DomainEvent, EventMetadata
from infrastructure.persistence.postgres_event_store import PostgresEventStore


@pytest.fixture()
async def session(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as s:
        yield s


def make_event(user_id: uuid.UUID, event_type: str) -> DomainEvent:
    return DomainEvent(
        event_type=event_type,
        version=1,
        aggregate_id=str(user_id),
        payload=dict(user_id=str(user_id)),
        metadata=EventMetadata(correlation_id="corr-1", user_id=str(user_id)),
    )


async def test_append_then_load_round_trip_preserves_order(session):
    store = PostgresEventStore(session)
    user_id = uuid.uuid4()
    first = make_event(user_id, "ProfileCreated")
    second = make_event(user_id, "BiometricConsentGranted")
    third = make_event(user_id, "WeightRecorded")

    await store.append(first)
    await store.append(second)
    await store.append(third)
    await session.commit()

    loaded = await store.load(user_id)
    assert [e.event_type for e in loaded] == [
        "ProfileCreated",
        "BiometricConsentGranted",
        "WeightRecorded",
    ]


async def test_load_unknown_aggregate_returns_empty_list_not_error(session):
    store = PostgresEventStore(session)
    loaded = await store.load(uuid.uuid4())
    assert loaded == []
