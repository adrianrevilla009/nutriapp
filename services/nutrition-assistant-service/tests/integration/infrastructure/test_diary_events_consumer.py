"""DiaryEventsConsumer -- against a real (testcontainers) RabbitMQ:
redelivering the same FoodEntryLogged event twice results in exactly one
projected row (idempotency, test plan section 3); a message that can
never be parsed is dead-lettered once it exhausts max_attempts
redeliveries. Mirrors analytics-service's DiaryEventsConsumer test
precedent exactly."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime

import aio_pika

from infrastructure.messaging.diary_events_consumer import (
    DLQ_NAME,
    EXCHANGE_NAME,
    DiaryEventsConsumer,
)
from infrastructure.persistence.postgres_diary_history_repository import (
    PostgresDiaryHistoryRepository,
)


def _food_entry_logged_body(entry_id: uuid.UUID, user_id: uuid.UUID, event_id: uuid.UUID) -> bytes:
    envelope = {
        "event_id": str(event_id),
        "aggregate_id": str(entry_id),
        "event_type": "FoodEntryLogged",
        "version": 1,
        "occurred_at": datetime.now(UTC).isoformat(),
        "payload": {
            "entry_id": str(entry_id),
            "user_id": str(user_id),
            "source": {
                "source_type": "catalog_product",
                "source_reference_id": "prod-1",
                "snapshot": {
                    "name": "Chicken breast",
                    "brand": None,
                    "quantity": 2.0,
                    "unit": "serving",
                    "macros_per_unit": {
                        "calories_kcal": 100.0,
                        "protein_g": 10.0,
                        "carbs_g": 0.0,
                        "fat_g": 2.0,
                    },
                },
            },
            "meal_slot": "lunch",
            "occurred_at": datetime.now(UTC).isoformat(),
            "planned_from_entry_id": None,
        },
        "metadata": {"correlation_id": "corr-1", "causation_id": None, "user_id": str(user_id)},
    }
    return json.dumps(envelope).encode("utf-8")


async def _publish(connection, routing_key: str, body: bytes) -> None:
    channel = await connection.channel()
    try:
        exchange = await channel.declare_exchange(
            EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )
        await exchange.publish(
            aio_pika.Message(body=body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key=routing_key,
        )
    finally:
        await channel.close()


async def _poll_diary_records(session_factory, user_id, *, attempts=20, interval=0.25):
    for _ in range(attempts):
        async with session_factory() as session:
            rows = await PostgresDiaryHistoryRepository(session).recent_for_user(user_id)
        if rows:
            return rows
        await asyncio.sleep(interval)
    return []


async def test_redelivering_the_same_food_entry_logged_event_applies_exactly_once(
    amqp_url, session_factory
):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = DiaryEventsConsumer(session_factory)
        await consumer.setup(connection)
        await consumer.consume()

        entry_id, user_id, event_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        body = _food_entry_logged_body(entry_id, user_id, event_id)

        await _publish(connection, "diary.food_entry.logged", body)
        await _publish(connection, "diary.food_entry.logged", body)

        rows = await _poll_diary_records(session_factory, user_id)
        await asyncio.sleep(0.5)  # let a possible second delivery finish processing

        assert len(rows) == 1  # applied exactly once, not twice
        assert "Chicken breast" in rows[0].content
    finally:
        await connection.close()


async def test_a_message_that_always_fails_is_dead_lettered_after_max_attempts(
    amqp_url, session_factory
):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = DiaryEventsConsumer(session_factory, max_attempts=1)
        await consumer.setup(connection)
        await consumer.consume()

        malformed_body = b"not valid json, will always raise while parsing"
        await _publish(connection, "diary.food_entry.logged", malformed_body)

        dlq_channel = await connection.channel()
        dead_letter_queue = await dlq_channel.declare_queue(DLQ_NAME, durable=True)

        received = await asyncio.wait_for(dead_letter_queue.get(timeout=10, fail=True), timeout=11)
        assert received.body == malformed_body
        await received.ack()
    finally:
        await connection.close()
