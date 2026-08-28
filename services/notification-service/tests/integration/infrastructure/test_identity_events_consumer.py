"""IdentityEventsConsumer -- against a real (testcontainers) RabbitMQ:
publishing the same event twice results in exactly one delivery attempt
(test-plan section 2's mandatory idempotency test); a handler that raises
is retried up to the configured limit, then dead-lettered."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import aio_pika
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from infrastructure.messaging.identity_events_consumer import (
    BINDING_ROUTING_KEY,
    DLQ_NAME,
    EXCHANGE_NAME,
    IdentityEventsConsumer,
)
from tests.fixtures.factories import (
    FakeEmailProviderPort,
    FakeTemplateRendererPort,
    FakeTokenRevealPort,
)

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "identity_events"


def _load_fixture(name: str) -> bytes:
    return json.dumps(json.loads((FIXTURES_DIR / name).read_text())).encode("utf-8")


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


async def test_redelivering_the_same_event_sends_exactly_once(amqp_url, session_factory):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        email_provider = FakeEmailProviderPort()
        consumer = IdentityEventsConsumer(
            session_factory, FakeTokenRevealPort(), email_provider, FakeTemplateRendererPort()
        )
        await consumer.setup(connection)
        await consumer.consume()

        body = _load_fixture("user_registered.json")
        await _publish(connection, "identity.user.registered", body)
        await _publish(connection, "identity.user.registered", body)

        for _ in range(20):
            if len(email_provider.calls) >= 1:
                break
            await asyncio.sleep(0.25)
        await asyncio.sleep(0.5)  # let a possible second delivery finish processing
        assert len(email_provider.calls) == 1
    finally:
        await connection.close()


async def test_new_device_alert_never_calls_reveal(amqp_url, session_factory):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        email_provider = FakeEmailProviderPort()
        token_reveal = FakeTokenRevealPort()
        consumer = IdentityEventsConsumer(
            session_factory, token_reveal, email_provider, FakeTemplateRendererPort()
        )
        await consumer.setup(connection)
        await consumer.consume()

        body = _load_fixture("new_device_login_detected.json")
        await _publish(connection, "identity.user.new_device_login_detected", body)

        for _ in range(20):
            if len(email_provider.calls) >= 1:
                break
            await asyncio.sleep(0.25)
        assert len(email_provider.calls) == 1
        assert len(token_reveal.calls) == 0
    finally:
        await connection.close()


async def test_a_message_that_always_fails_is_dead_lettered_after_max_attempts(
    amqp_url, session_factory
):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = IdentityEventsConsumer(
            session_factory,
            FakeTokenRevealPort(),
            FakeEmailProviderPort(),
            FakeTemplateRendererPort(),
            max_attempts=1,
        )
        await consumer.setup(connection)
        await consumer.consume()

        malformed_body = b"not valid json, will always raise while parsing"
        await _publish(
            connection, BINDING_ROUTING_KEY.replace("#", "user.registered"), malformed_body
        )

        dlq_channel = await connection.channel()
        dlq = await dlq_channel.declare_queue(DLQ_NAME, durable=True)

        received = await asyncio.wait_for(dlq.get(timeout=10, fail=True), timeout=11)
        assert received.body == malformed_body
        await received.ack()
    finally:
        await connection.close()
