from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.events.base import DomainEvent, EventMetadata
from domain.ports.event_store_port import OptimisticConcurrencyError
from infrastructure.persistence.postgres_event_store import PostgresEventStore


@pytest.fixture
async def session(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as s:
        yield s


def make_event(aggregate_id: str, event_type: str) -> DomainEvent:
    return DomainEvent(
        event_type=event_type,
        version=1,
        aggregate_id=aggregate_id,
        payload=dict(user_id=str(uuid.uuid4())),
        metadata=EventMetadata(correlation_id="corr-1"),
    )


@pytest.mark.parametrize(
    "aggregate_type",
    ["food_entry", "water_intake_entry", "fasting_window", "meal_plan_entry"],
)
async def test_append_then_load_round_trip_preserves_order(session, aggregate_type):
    store = PostgresEventStore(session)
    aggregate_id = str(uuid.uuid4())
    first = make_event(aggregate_id, "FirstEvent")
    second = make_event(aggregate_id, "SecondEvent")

    await store.append(aggregate_type, first, expected_version=0)
    await store.append(aggregate_type, second, expected_version=1)
    await session.commit()

    loaded = await store.load(aggregate_type, aggregate_id)
    assert [e.event_type for e in loaded] == ["FirstEvent", "SecondEvent"]


async def test_load_unknown_aggregate_returns_empty_list_not_error(session):
    store = PostgresEventStore(session)
    loaded = await store.load("food_entry", str(uuid.uuid4()))
    assert loaded == []


async def test_no_cross_contamination_between_aggregate_types_sharing_the_same_id(session):
    """Two different aggregate_types happening to share the same
    aggregate_id string must not see each other's events -- proves the
    single diary_events table's aggregate_type discriminator actually
    isolates streams (implementation plan section 9.5)."""
    store = PostgresEventStore(session)
    shared_id = str(uuid.uuid4())
    food_event = make_event(shared_id, "FoodEntryLogged")
    water_event = make_event(shared_id, "WaterIntakeLogged")

    await store.append("food_entry", food_event, expected_version=0)
    await store.append("water_intake_entry", water_event, expected_version=0)
    await session.commit()

    food_stream = await store.load("food_entry", shared_id)
    water_stream = await store.load("water_intake_entry", shared_id)
    assert [e.event_type for e in food_stream] == ["FoodEntryLogged"]
    assert [e.event_type for e in water_stream] == ["WaterIntakeLogged"]


async def test_concurrent_append_to_same_aggregate_is_serialized(db_engine, postgres_async_url):
    """Simulates a race: two independent sessions both load an empty
    stream (expected_version=0) and attempt to append -- exactly one must
    succeed, the other must raise OptimisticConcurrencyError (test-plan
    section 2)."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(postgres_async_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    aggregate_id = str(uuid.uuid4())

    async def attempt() -> bool:
        async with session_factory() as session:
            store = PostgresEventStore(session)
            event = make_event(aggregate_id, "FoodEntryLogged")
            try:
                await store.append("food_entry", event, expected_version=0)
                await session.commit()
                return True
            except OptimisticConcurrencyError:
                return False

    results = await asyncio.gather(attempt(), attempt())
    await engine.dispose()
    assert sorted(results) == [False, True]
