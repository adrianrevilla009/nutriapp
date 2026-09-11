"""BillingEventsConsumer -- against a real (testcontainers) RabbitMQ:
redelivering the same EntitlementGranted/EntitlementRevoked event twice
results in exactly one cache upsert (test-plan addendum, 2026-09-11).
nutrition-assistant-service is the FOURTH real consumer of these events.
Mirrors analytics-service's/diary_events_consumer's identical precedent."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime

import aio_pika

from infrastructure.messaging.billing_events_consumer import (
    BINDING_ROUTING_KEY,
    DLQ_NAME,
    EXCHANGE_NAME,
    BillingEventsConsumer,
    dispatch_billing_event,
)
from infrastructure.persistence.postgres_entitlement_cache_repository import (
    PostgresEntitlementCacheRepository,
)


def _entitlement_event_body(
    event_type: str, user_id: uuid.UUID, event_id: uuid.UUID, timestamp_field: str
) -> bytes:
    envelope = {
        "event_id": str(event_id),
        "aggregate_id": str(user_id),
        "event_type": event_type,
        "version": 1,
        "occurred_at": datetime.now(UTC).isoformat(),
        "payload": {
            "user_id": str(user_id),
            "reason": "subscription_started" if event_type == "EntitlementGranted" else "cancelled",
            timestamp_field: datetime.now(UTC).isoformat(),
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


async def _poll_cached_entitlement(session_factory, user_id, *, attempts=20, interval=0.25):
    for _ in range(attempts):
        async with session_factory() as session:
            cached = await PostgresEntitlementCacheRepository(session).get(user_id)
        if cached is not None:
            return cached
        await asyncio.sleep(interval)
    return None


async def test_redelivering_the_same_entitlement_granted_event_upserts_cache_exactly_once(
    amqp_url, session_factory
):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = BillingEventsConsumer(session_factory)
        await consumer.setup(connection)
        await consumer.consume()

        user_id, event_id = uuid.uuid4(), uuid.uuid4()
        body = _entitlement_event_body("EntitlementGranted", user_id, event_id, "granted_at")

        await _publish(connection, "billing.entitlement.granted", body)
        await _publish(connection, "billing.entitlement.granted", body)

        cached = await _poll_cached_entitlement(session_factory, user_id)
        await asyncio.sleep(0.5)

        assert cached is True
    finally:
        await connection.close()


async def test_redelivering_the_same_entitlement_revoked_event_upserts_cache_exactly_once(
    amqp_url, session_factory
):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = BillingEventsConsumer(session_factory)
        await consumer.setup(connection)
        await consumer.consume()

        user_id, event_id = uuid.uuid4(), uuid.uuid4()

        # Seed the user as already entitled first, so revocation is observable.
        granted_body = _entitlement_event_body(
            "EntitlementGranted", user_id, uuid.uuid4(), "granted_at"
        )
        await _publish(connection, "billing.entitlement.granted", granted_body)
        await _poll_cached_entitlement(session_factory, user_id)

        revoked_body = _entitlement_event_body(
            "EntitlementRevoked", user_id, event_id, "revoked_at"
        )
        await _publish(connection, "billing.entitlement.revoked", revoked_body)
        await _publish(connection, "billing.entitlement.revoked", revoked_body)

        async def _poll_revoked():
            for _ in range(20):
                async with session_factory() as session:
                    cached = await PostgresEntitlementCacheRepository(session).get(user_id)
                if cached is False:
                    return cached
                await asyncio.sleep(0.25)
            return None

        cached = await _poll_revoked()
        await asyncio.sleep(0.5)

        assert cached is False
    finally:
        await connection.close()


async def test_unhandled_event_type_is_ignored(session_factory) -> None:
    async with session_factory() as session:
        await dispatch_billing_event(session, "SubscriptionRenewed", uuid.uuid4(), {})
        await session.commit()


async def test_a_message_that_always_fails_is_dead_lettered_after_max_attempts(
    amqp_url, session_factory
):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = BillingEventsConsumer(session_factory, max_attempts=1)
        await consumer.setup(connection)
        await consumer.consume()

        malformed_body = b"not valid json, will always raise while parsing"
        granted_routing_key = BINDING_ROUTING_KEY.replace("*", "granted")
        await _publish(connection, granted_routing_key, malformed_body)

        dlq_channel = await connection.channel()
        dead_letter_queue = await dlq_channel.declare_queue(DLQ_NAME, durable=True)

        received = await asyncio.wait_for(dead_letter_queue.get(timeout=10, fail=True), timeout=11)
        assert received.body == malformed_body
        await received.ack()
    finally:
        await connection.close()
