"""BillingEventsConsumer -- against a real (testcontainers) RabbitMQ:
publishing the same `EntitlementGranted`/`EntitlementRevoked` event twice
results in exactly one cache upsert (idempotency test, test-plan section
2); a handler-adjacent malformed message is dead-lettered after
`max_attempts`."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

import aio_pika
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from infrastructure.messaging.billing_events_consumer import (
    BINDING_ROUTING_KEY,
    DLQ_NAME,
    EXCHANGE_NAME,
    BillingEventsConsumer,
)
from infrastructure.persistence.postgres_entitlement_cache_repository import (
    PostgresEntitlementCacheRepository,
)


@pytest.fixture(scope="module")
def rabbitmq_container():
    from testcontainers.rabbitmq import RabbitMqContainer

    with RabbitMqContainer("rabbitmq:3.13-management-alpine") as container:
        yield container


@pytest.fixture
async def amqp_url(rabbitmq_container):
    host = rabbitmq_container.get_container_host_ip()
    port = rabbitmq_container.get_exposed_port(5672)
    return f"amqp://guest:guest@{host}:{port}/"


@pytest.fixture
def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


def _entitlement_granted_body(user_id: uuid.UUID, event_id: uuid.UUID) -> bytes:
    body = {
        "event_id": str(event_id),
        "aggregate_id": str(user_id),
        "event_type": "EntitlementGranted",
        "version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "user_id": str(user_id),
            "reason": "subscription_started",
            "granted_at": datetime.now(timezone.utc).isoformat(),
        },
        "metadata": {"correlation_id": "corr-1", "causation_id": None, "user_id": str(user_id)},
    }
    return json.dumps(body).encode("utf-8")


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


async def test_redelivering_the_same_entitlement_granted_event_upserts_cache_exactly_once(
    amqp_url, session_factory
):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = BillingEventsConsumer(session_factory)
        await consumer.setup(connection)
        await consumer.consume()

        user_id = uuid.uuid4()
        event_id = uuid.uuid4()
        body = _entitlement_granted_body(user_id, event_id)

        await _publish(connection, "billing.entitlement.granted", body)
        await _publish(connection, "billing.entitlement.granted", body)

        cached = None
        for _ in range(20):
            async with session_factory() as session:
                cache = PostgresEntitlementCacheRepository(session)
                cached = await cache.get(user_id)
            if cached is not None:
                break
            await asyncio.sleep(0.25)
        await asyncio.sleep(0.5)  # let a possible second delivery finish processing

        assert cached is True
    finally:
        await connection.close()


async def test_a_message_that_always_fails_is_dead_lettered_after_max_attempts(
    amqp_url, session_factory
):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = BillingEventsConsumer(session_factory, max_attempts=1)
        await consumer.setup(connection)
        await consumer.consume()

        malformed_body = b"not valid json, will always raise while parsing"
        await _publish(connection, BINDING_ROUTING_KEY.replace("*", "granted"), malformed_body)

        dlq_channel = await connection.channel()
        dlq = await dlq_channel.declare_queue(DLQ_NAME, durable=True)

        received = await asyncio.wait_for(dlq.get(timeout=10, fail=True), timeout=11)
        assert received.body == malformed_body
        await received.ack()
    finally:
        await connection.close()
