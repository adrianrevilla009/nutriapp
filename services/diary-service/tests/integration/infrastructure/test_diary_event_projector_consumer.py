"""DiaryEventProjectorConsumer: consumes this service's own published
events and idempotently projects them; a message that keeps failing is
retried up to the configured limit then routed to the dead-letter queue
(test-plan section 2/5, acceptance criterion 8's mandatory idempotency
test)."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

import aio_pika
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.entities.food_entry import FoodEntry
from domain.value_objects.food_source import FoodSource, FoodSourceSnapshot
from domain.value_objects.macro_snapshot import MacroSnapshot
from domain.value_objects.meal_slot import MealSlot
from infrastructure.messaging.diary_event_projector_consumer import (
    BINDING_ROUTING_KEY,
    DLQ_NAME,
    EXCHANGE_NAME,
    DiaryEventProjectorConsumer,
)
from infrastructure.persistence.models import FoodEntryViewModel
from infrastructure.persistence.projectors.food_entries_projector import (
    PostgresFoodEntriesProjector,
)

NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def rabbitmq_container():
    from testcontainers.rabbitmq import RabbitMqContainer

    with RabbitMqContainer("rabbitmq:3.13-management-alpine") as container:
        yield container


@pytest.fixture()
async def amqp_url(rabbitmq_container):
    host = rabbitmq_container.get_container_host_ip()
    port = rabbitmq_container.get_exposed_port(5672)
    return f"amqp://guest:guest@{host}:{port}/"


@pytest.fixture()
def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


def _food_entry_logged_event():
    entry_id = uuid.uuid4()
    user_id = uuid.uuid4()
    source = FoodSource(
        source_type="catalog_product",
        source_reference_id="prod-1",
        snapshot=FoodSourceSnapshot(
            name="Oats",
            brand=None,
            quantity=100.0,
            unit="g",
            macros_per_unit=MacroSnapshot(calories_kcal=100, protein_g=5, carbs_g=10, fat_g=2),
        ),
    )
    _entry, event = FoodEntry.log(
        entry_id=entry_id,
        user_id=user_id,
        source=source,
        meal_slot=MealSlot.BREAKFAST,
        occurred_at=NOW,
        correlation_id="corr-1",
    )
    return event


async def _publish(connection, routing_key: str, body: bytes) -> None:
    channel = await connection.channel()
    exchange = await channel.declare_exchange(
        EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
    )
    await exchange.publish(
        aio_pika.Message(body=body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
        routing_key=routing_key,
    )
    await channel.close()


async def test_valid_event_is_projected(amqp_url, session_factory):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = DiaryEventProjectorConsumer(session_factory)
        await consumer.setup(connection)
        await consumer.consume()

        event = _food_entry_logged_event()
        await _publish(
            connection, "diary.food_entry.logged", json.dumps(event.to_wire()).encode("utf-8")
        )

        entry_id = uuid.UUID(event.payload["entry_id"])

        async def _projected() -> bool:
            async with session_factory() as session:
                row = await session.get(FoodEntryViewModel, entry_id)
                return row is not None

        for _ in range(20):
            if await _projected():
                break
            await asyncio.sleep(0.25)
        assert await _projected()
    finally:
        await connection.close()


async def test_redelivering_the_same_event_id_does_not_double_project(amqp_url, session_factory):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = DiaryEventProjectorConsumer(session_factory)
        await consumer.setup(connection)
        await consumer.consume()

        event = _food_entry_logged_event()
        entry_id = uuid.UUID(event.payload["entry_id"])
        body = json.dumps(event.to_wire()).encode("utf-8")

        await _publish(connection, "diary.food_entry.logged", body)
        await _publish(connection, "diary.food_entry.logged", body)

        async def _row_count() -> int:
            async with session_factory() as session:
                result = await session.execute(
                    select(FoodEntryViewModel).where(FoodEntryViewModel.entry_id == entry_id)
                )
                return len(list(result.scalars()))

        for _ in range(20):
            if await _row_count() >= 1:
                break
            await asyncio.sleep(0.25)
        await asyncio.sleep(0.5)  # let a possible second delivery finish processing
        assert await _row_count() == 1

        async with session_factory() as session:
            read_port = PostgresFoodEntriesProjector(session)
            summary_rows = await read_port.list_entries(
                uuid.UUID(event.payload["user_id"]), None, None
            )
            assert len(summary_rows) == 1
    finally:
        await connection.close()


async def test_a_message_that_always_fails_is_dead_lettered_after_max_attempts(
    amqp_url, session_factory
):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = DiaryEventProjectorConsumer(session_factory, max_attempts=1)
        await consumer.setup(connection)
        await consumer.consume()

        malformed_body = b"not valid json, will always raise while parsing"
        await _publish(
            connection, BINDING_ROUTING_KEY.replace("#", "food_entry.logged"), malformed_body
        )

        dlq_channel = await connection.channel()
        dlq = await dlq_channel.declare_queue(DLQ_NAME, durable=True)

        received = await asyncio.wait_for(dlq.get(timeout=10, fail=True), timeout=11)
        assert received.body == malformed_body
        await received.ack()
    finally:
        await connection.close()
