"""OutboxRelayWorker end-to-end: Postgres outbox row -> relayed onto
RabbitMQ -> marked published, not republished on a second relay pass.
"""

from __future__ import annotations

import asyncio
import json

import aio_pika
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from testcontainers.rabbitmq import RabbitMqContainer

from domain.events.user_registered import build_user_registered_event
from infrastructure.messaging.outbox_relay_worker import OutboxRelayWorker
from infrastructure.messaging.rabbitmq_event_publisher import (
    EXCHANGE_NAME,
    RabbitMqEventPublisher,
    routing_key_for,
)
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository


@pytest.fixture(scope="module")
def rabbitmq_container():
    with RabbitMqContainer("rabbitmq:3.13-management-alpine") as container:
        yield container


@pytest.fixture()
async def amqp_url(rabbitmq_container):
    host = rabbitmq_container.get_container_host_ip()
    port = rabbitmq_container.get_exposed_port(5672)
    return f"amqp://guest:guest@{host}:{port}/"


async def test_outbox_relay_worker__relays_pending_events_and_does_not_republish(
    db_engine, amqp_url
):
    import uuid

    event = build_user_registered_event(
        user_id=uuid.uuid4(),
        email="relay@example.com",
        registered_at_iso="2026-01-01T00:00:00+00:00",
        email_verification_token_reference_id=uuid.uuid4(),
        correlation_id="corr-1",
    )
    async with AsyncSession(db_engine) as session:
        outbox = PostgresOutboxRepository(session)
        await outbox.enqueue(event)
        await session.commit()

    connection = await aio_pika.connect_robust(amqp_url)
    try:
        publisher = await RabbitMqEventPublisher.create(connection)
        consumer_channel = await connection.channel()
        exchange = await consumer_channel.declare_exchange(
            EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )
        queue = await consumer_channel.declare_queue(exclusive=True)
        await queue.bind(exchange, routing_key=routing_key_for("UserRegistered"))

        def session_factory():
            return AsyncSession(db_engine)

        worker = OutboxRelayWorker(session_factory, publisher)
        relayed_count = await worker.relay_once()
        assert relayed_count == 1

        message = await asyncio.wait_for(queue.get(timeout=5, fail=True), timeout=6)
        body = json.loads(message.body)
        assert body["event_id"] == str(event.event_id)
        await message.ack()

        # Second pass relays nothing new.
        second_pass_count = await worker.relay_once()
        assert second_pass_count == 0
    finally:
        await connection.close()
