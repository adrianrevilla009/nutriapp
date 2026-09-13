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
from infrastructure.persistence.models import (
    MicronutrientCurrentTargetModel,
    MicronutrientWindowModel,
)

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


def _target_updated_body(
    user_id: uuid.UUID, event_id: uuid.UUID, *, nutrient_targets_min: dict | None
) -> bytes:
    """Addendum 2026-09-12: `nutrient_targets_min` is the real, confirmed
    field name/shape from nutrition-calculation-service (flat
    `dict[str, float]`, additive, still v1) -- passing `None` here
    simulates an "old-shaped" event published before that field existed at
    all, exercising the `macro_targets`-sourced backward-compat fallback."""
    payload: dict = {
        "user_id": str(user_id),
        "bmr_kcal": 1600.0,
        "tdee_kcal": 2200.0,
        "calorie_target_kcal": 2000.0,
        "macro_targets": {
            "protein_g_min": 50.0,
            "protein_g_max": 150.0,
            "fat_g_min": 44.0,
            "carbs_g": 250.0,
        },
        "goal_type": "MAINTAIN",
        "activity_level": "MODERATE",
        "activity_adjustment_kcal": None,
        "clamped": False,
        "clamp_reason": None,
        "formula_version": "v1",
        "reason": "weight_recorded",
        "effective_from": datetime.now(timezone.utc).isoformat(),
    }
    if nutrient_targets_min is not None:
        payload["nutrient_targets_min"] = nutrient_targets_min
    envelope = {
        "event_id": str(event_id),
        "aggregate_id": str(user_id),
        "event_type": "NutritionTargetUpdated",
        "version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
        "metadata": {"correlation_id": "corr-target-1", "causation_id": None, "user_id": str(user_id)},
    }
    return json.dumps(envelope).encode("utf-8")


async def _poll_current_targets(session_factory, user_id, *, attempts=20, interval=0.25):
    for _ in range(attempts):
        async with session_factory() as session:
            stmt = select(MicronutrientCurrentTargetModel).where(
                MicronutrientCurrentTargetModel.user_id == user_id
            )
            rows = (await session.execute(stmt)).scalars().all()
        if rows:
            return {row.nutrient: row.target_min for row in rows}
        await asyncio.sleep(interval)
    return {}


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


async def test_nutrition_target_updated_stores_all_five_target_min_values(
    amqp_url, session_factory
):
    """Addendum 2026-09-12: a NutritionTargetUpdated with a full 5-key
    `nutrient_targets_min` map results in all 5 being stored in
    `micronutrient_current_targets`, sourced from that map (not
    `macro_targets`)."""
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = NutritionCalculationEventsConsumer(session_factory)
        await consumer.setup(connection)
        await consumer.consume()

        user_id, event_id = uuid.uuid4(), uuid.uuid4()
        body = _target_updated_body(
            user_id,
            event_id,
            nutrient_targets_min={
                "protein_g": 55.0,
                "fat_g": 40.0,
                "calcium_mg": 1000.0,
                "iron_mg": 8.0,
                "vitamin_c_mg": 90.0,
            },
        )

        await _publish(connection, "nutrition-calculation.target.updated", body)

        targets = await _poll_current_targets(session_factory, user_id)

        assert targets == {
            "protein_g": 55.0,
            "fat_g": 40.0,
            "calcium_mg": 1000.0,
            "iron_mg": 8.0,
            "vitamin_c_mg": 90.0,
        }
    finally:
        await connection.close()


async def test_nutrition_target_updated_without_nutrient_targets_min_falls_back_to_macro_targets(
    amqp_url, session_factory
):
    """Backward compatibility: an "old-shaped" event published before
    `nutrient_targets_min` existed at all must still resolve protein_g/fat_g
    via `macro_targets`, while the 3 newer keys resolve to None -- never
    fabricated from any other field."""
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = NutritionCalculationEventsConsumer(session_factory)
        await consumer.setup(connection)
        await consumer.consume()

        user_id, event_id = uuid.uuid4(), uuid.uuid4()
        body = _target_updated_body(user_id, event_id, nutrient_targets_min=None)

        await _publish(connection, "nutrition-calculation.target.updated", body)

        targets = await _poll_current_targets(session_factory, user_id)

        assert targets["protein_g"] == 50.0  # via macro_targets.protein_g_min fallback
        assert targets["fat_g"] == 44.0  # via macro_targets.fat_g_min fallback
        assert targets["calcium_mg"] is None
        assert targets["iron_mg"] is None
        assert targets["vitamin_c_mg"] is None
    finally:
        await connection.close()


async def test_nutrition_target_updated_under_19_user_has_none_for_dri_gated_keys(
    amqp_url, session_factory
):
    """A `nutrient_targets_min` present but only carrying protein_g/fat_g
    (e.g. an under-19 user, no resolved DRI minimum) leaves the 3 newer
    keys as None, not defaulted."""
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = NutritionCalculationEventsConsumer(session_factory)
        await consumer.setup(connection)
        await consumer.consume()

        user_id, event_id = uuid.uuid4(), uuid.uuid4()
        body = _target_updated_body(
            user_id, event_id, nutrient_targets_min={"protein_g": 50.0, "fat_g": 44.0}
        )

        await _publish(connection, "nutrition-calculation.target.updated", body)

        targets = await _poll_current_targets(session_factory, user_id)

        assert targets["protein_g"] == 50.0
        assert targets["fat_g"] == 44.0
        assert targets["calcium_mg"] is None
        assert targets["iron_mg"] is None
        assert targets["vitamin_c_mg"] is None
    finally:
        await connection.close()


async def test_redelivering_the_same_target_updated_event_does_not_double_write(
    amqp_url, session_factory
):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = NutritionCalculationEventsConsumer(session_factory)
        await consumer.setup(connection)
        await consumer.consume()

        user_id, event_id = uuid.uuid4(), uuid.uuid4()
        body = _target_updated_body(
            user_id,
            event_id,
            nutrient_targets_min={
                "protein_g": 55.0,
                "fat_g": 40.0,
                "calcium_mg": 1000.0,
                "iron_mg": 8.0,
                "vitamin_c_mg": 90.0,
            },
        )

        await _publish(connection, "nutrition-calculation.target.updated", body)
        await _publish(connection, "nutrition-calculation.target.updated", body)

        targets = await _poll_current_targets(session_factory, user_id)
        await asyncio.sleep(0.5)

        async with session_factory() as session:
            stmt = select(MicronutrientCurrentTargetModel).where(
                MicronutrientCurrentTargetModel.user_id == user_id
            )
            rows = (await session.execute(stmt)).scalars().all()

        assert len(rows) == 5  # one row per tracked nutrient, never duplicated
        assert targets["calcium_mg"] == 1000.0
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
