"""NutritionCalculationEventsConsumer -- redelivering the same
`NutritionValueRecomputed` event twice results in exactly one
micronutrient_window upsert (idempotency); a message that can never be
parsed is dead-lettered once it exhausts `max_attempts` redeliveries
(DLQ parity with `diary_events_consumer`/`billing_events_consumer`'s
existing tests)."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import date, datetime, timezone

import aio_pika
from sqlalchemy import select

from infrastructure.messaging.nutrition_calculation_events_consumer import (
    DLQ_NAME,
    EXCHANGE_NAME,
    NutritionCalculationEventsConsumer,
)
from infrastructure.persistence.models import MicronutrientWindowModel

TODAY = date(2026, 6, 8)


def _value_recomputed_body(user_id: uuid.UUID, event_id: uuid.UUID) -> bytes:
    envelope = {
        "event_id": str(event_id),
        "aggregate_id": str(user_id),
        "event_type": "NutritionValueRecomputed",
        "version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "user_id": str(user_id),
            "scope": "day",
            "entry_id": None,
            "date": TODAY.isoformat(),
            "macros": {
                "calories_kcal": 1800.0,
                "protein_g": 40.0,
                "carbs_g": 200.0,
                "fat_g": 30.0,
            },
            "micronutrients": None,
            "micronutrients_status": "unavailable",
            "is_estimated": False,
            "confidence_range": None,
            "formula_version": "v1",
            "reason": "food_entry_logged",
            "recomputed_at": datetime.now(timezone.utc).isoformat(),
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


async def _poll_window_row_count(session_factory, user_id, *, attempts=20, interval=0.25):
    for _ in range(attempts):
        async with session_factory() as session:
            stmt = select(MicronutrientWindowModel).where(
                MicronutrientWindowModel.user_id == user_id,
                MicronutrientWindowModel.nutrient == "protein_g",
            )
            rows = (await session.execute(stmt)).scalars().all()
        if rows:
            return len(rows)
        await asyncio.sleep(interval)
    return 0


async def test_redelivering_the_same_value_recomputed_event_upserts_exactly_once(
    amqp_url, session_factory
):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = NutritionCalculationEventsConsumer(session_factory)
        await consumer.setup(connection)
        await consumer.consume()

        user_id, event_id = uuid.uuid4(), uuid.uuid4()
        body = _value_recomputed_body(user_id, event_id)

        await _publish(connection, "nutrition-calculation.target.recomputed", body)
        await _publish(connection, "nutrition-calculation.target.recomputed", body)

        count = await _poll_window_row_count(session_factory, user_id)
        await asyncio.sleep(0.5)

        assert count == 1  # exactly one (user, nutrient, date) row -- upsert, not insert-twice
    finally:
        await connection.close()


async def test_a_message_that_always_fails_is_dead_lettered_after_max_attempts(
    amqp_url, session_factory
):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = NutritionCalculationEventsConsumer(session_factory, max_attempts=1)
        await consumer.setup(connection)
        await consumer.consume()

        malformed_body = b"not valid json, will always raise while parsing"
        await _publish(connection, "nutrition-calculation.target.recomputed", malformed_body)

        dlq_channel = await connection.channel()
        dead_letter_queue = await dlq_channel.declare_queue(DLQ_NAME, durable=True)

        received = await asyncio.wait_for(dead_letter_queue.get(timeout=10, fail=True), timeout=11)
        assert received.body == malformed_body
        await received.ack()
    finally:
        await connection.close()
