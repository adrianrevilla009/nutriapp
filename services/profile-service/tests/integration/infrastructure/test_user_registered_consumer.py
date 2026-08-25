"""UserRegisteredConsumer: consumes identity-service's UserRegistered
(v1), idempotently creates a profile; a message that keeps failing is
retried up to the configured limit then routed to the dead-letter queue
(test-plan section 2)."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

import aio_pika
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from testcontainers.rabbitmq import RabbitMqContainer

from infrastructure.messaging.user_registered_consumer import (
    DLQ_NAME,
    IDENTITY_EXCHANGE_NAME,
    IDENTITY_USER_REGISTERED_ROUTING_KEY,
    UserRegisteredConsumer,
)
from infrastructure.persistence.postgres_event_store import PostgresEventStore


@pytest.fixture(scope="module")
def rabbitmq_container():
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


def _user_registered_wire_message(user_id: uuid.UUID, event_id: uuid.UUID | None = None) -> bytes:
    body = dict(
        event_id=str(event_id or uuid.uuid4()),
        aggregate_id=str(user_id),
        event_type="UserRegistered",
        version=1,
        occurred_at=datetime.now(timezone.utc).isoformat(),
        payload=dict(
            user_id=str(user_id),
            email="user@example.com",
            registered_at=datetime.now(timezone.utc).isoformat(),
            email_verification_token_reference_id=str(uuid.uuid4()),
        ),
        metadata=dict(correlation_id="corr-1", causation_id=None, user_id=str(user_id)),
    )
    return json.dumps(body).encode("utf-8")


async def _publish_identity_event(connection, routing_key: str, body: bytes) -> None:
    channel = await connection.channel()
    exchange = await channel.declare_exchange(
        IDENTITY_EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
    )
    await exchange.publish(
        aio_pika.Message(body=body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
        routing_key=routing_key,
    )
    await channel.close()


async def test_valid_user_registered_creates_profile(amqp_url, session_factory):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = UserRegisteredConsumer(session_factory)
        await consumer.setup(connection)
        await consumer.consume()

        user_id = uuid.uuid4()
        await _publish_identity_event(
            connection,
            IDENTITY_USER_REGISTERED_ROUTING_KEY,
            _user_registered_wire_message(user_id),
        )

        async def _profile_exists() -> bool:
            async with session_factory() as session:
                events = await PostgresEventStore(session).load(user_id)
                return any(e.event_type == "ProfileCreated" for e in events)

        for _ in range(20):
            if await _profile_exists():
                break
            await asyncio.sleep(0.25)
        assert await _profile_exists()
    finally:
        await connection.close()


async def test_redelivering_the_same_event_id_does_not_double_create_a_profile(
    amqp_url, session_factory
):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = UserRegisteredConsumer(session_factory)
        await consumer.setup(connection)
        await consumer.consume()

        user_id = uuid.uuid4()
        source_event_id = uuid.uuid4()
        message = _user_registered_wire_message(user_id, event_id=source_event_id)

        await _publish_identity_event(connection, IDENTITY_USER_REGISTERED_ROUTING_KEY, message)
        await _publish_identity_event(connection, IDENTITY_USER_REGISTERED_ROUTING_KEY, message)

        async def _profile_created_count() -> int:
            async with session_factory() as session:
                events = await PostgresEventStore(session).load(user_id)
                return len([e for e in events if e.event_type == "ProfileCreated"])

        for _ in range(20):
            if await _profile_created_count() >= 1:
                break
            await asyncio.sleep(0.25)
        await asyncio.sleep(0.5)  # let a possible second delivery finish processing
        assert await _profile_created_count() == 1
    finally:
        await connection.close()


async def test_a_message_that_always_fails_is_dead_lettered_after_max_attempts(
    amqp_url, session_factory
):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = UserRegisteredConsumer(session_factory, max_attempts=1)
        await consumer.setup(connection)
        await consumer.consume()

        malformed_body = b"not valid json, will always raise while parsing"
        await _publish_identity_event(
            connection, IDENTITY_USER_REGISTERED_ROUTING_KEY, malformed_body
        )

        dlq_channel = await connection.channel()
        dlq = await dlq_channel.declare_queue(DLQ_NAME, durable=True)

        received = await asyncio.wait_for(dlq.get(timeout=10, fail=True), timeout=11)
        assert received.body == malformed_body
        await received.ack()
    finally:
        await connection.close()
