"""ProfileEventsConsumer -- redelivering the same `WeightRecorded` event
twice results in exactly one weight_trend row (idempotency); a message
that can never be parsed is dead-lettered once it exhausts `max_attempts`
redeliveries (DLQ parity with `diary_events_consumer`/
`billing_events_consumer`'s existing tests -- the underlying
`_retry_or_dead_letter` mechanism is shared via `ResilientTopicConsumer`,
but this is the first test exercising it through THIS consumer's own
queue/exchange wiring)."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

import aio_pika

from infrastructure.messaging.profile_events_consumer import (
    DLQ_NAME,
    EXCHANGE_NAME,
    ProfileEventsConsumer,
)
from infrastructure.persistence.models import WeightTrendModel


def _weight_recorded_body(user_id: uuid.UUID, event_id: uuid.UUID, recorded_at: datetime) -> bytes:
    envelope = {
        "event_id": str(event_id),
        "aggregate_id": str(user_id),
        "event_type": "WeightRecorded",
        "version": 1,
        "occurred_at": recorded_at.isoformat(),
        "payload": {
            "user_id": str(user_id),
            "weight_kg": "ciphertext==",
            "recorded_at": recorded_at.isoformat(),
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


async def _poll_row_count(session_factory, user_id, on_date, *, attempts=20, interval=0.25):
    from sqlalchemy import select

    for _ in range(attempts):
        async with session_factory() as session:
            stmt = select(WeightTrendModel).where(
                WeightTrendModel.user_id == user_id, WeightTrendModel.on_date == on_date
            )
            rows = (await session.execute(stmt)).scalars().all()
        if rows:
            return len(rows)
        await asyncio.sleep(interval)
    return 0


async def test_redelivering_the_same_weight_recorded_event_upserts_exactly_once(
    amqp_url, session_factory
):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = ProfileEventsConsumer(session_factory)
        await consumer.setup(connection)
        await consumer.consume()

        user_id, event_id = uuid.uuid4(), uuid.uuid4()
        recorded_at = datetime.now(timezone.utc)
        body = _weight_recorded_body(user_id, event_id, recorded_at)

        await _publish(connection, "profile.profile.weight_recorded", body)
        await _publish(connection, "profile.profile.weight_recorded", body)

        count = await _poll_row_count(session_factory, user_id, recorded_at.date())
        await asyncio.sleep(0.5)

        assert count == 1
    finally:
        await connection.close()


async def test_a_message_that_always_fails_is_dead_lettered_after_max_attempts(
    amqp_url, session_factory
):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = ProfileEventsConsumer(session_factory, max_attempts=1)
        await consumer.setup(connection)
        await consumer.consume()

        malformed_body = b"not valid json, will always raise while parsing"
        await _publish(connection, "profile.profile.weight_recorded", malformed_body)

        dlq_channel = await connection.channel()
        dead_letter_queue = await dlq_channel.declare_queue(DLQ_NAME, durable=True)

        received = await asyncio.wait_for(dead_letter_queue.get(timeout=10, fail=True), timeout=11)
        assert received.body == malformed_body
        await received.ack()
    finally:
        await connection.close()
