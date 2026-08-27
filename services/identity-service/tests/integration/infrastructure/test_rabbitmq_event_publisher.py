"""RabbitMqEventPublisher: publishes to the correct exchange/routing key
per messaging-conventions SKILL.md naming, consumable by a test subscriber.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import aio_pika
import pytest
from testcontainers.rabbitmq import RabbitMqContainer

from domain.events.new_device_login_detected import build_new_device_login_detected_event
from infrastructure.messaging.rabbitmq_event_publisher import (
    EXCHANGE_NAME,
    RabbitMqEventPublisher,
    routing_key_for,
)


@pytest.fixture(scope="module")
def rabbitmq_container():
    with RabbitMqContainer("rabbitmq:3.13-management-alpine") as container:
        yield container


@pytest.fixture()
async def amqp_url(rabbitmq_container):
    host = rabbitmq_container.get_container_host_ip()
    port = rabbitmq_container.get_exposed_port(5672)
    return f"amqp://guest:guest@{host}:{port}/"


async def test_rabbitmq_publisher__publishes_to_correct_exchange_and_routing_key__consumable(
    amqp_url,
):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        publisher = await RabbitMqEventPublisher.create(connection)

        consumer_channel = await connection.channel()
        exchange = await consumer_channel.declare_exchange(
            EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )
        queue = await consumer_channel.declare_queue(exclusive=True)
        routing_key = routing_key_for("NewDeviceLoginDetected")
        assert routing_key == "identity.user.new_device_login_detected"
        await queue.bind(exchange, routing_key=routing_key)

        event = build_new_device_login_detected_event(
            user_id=uuid.uuid4(),
            device_fingerprint_hash="fp-hash",
            occurred_at_iso="2026-01-01T00:00:00+00:00",
            email="user@example.com",
            correlation_id="corr-1",
        )
        await publisher.publish(event)

        received = await asyncio.wait_for(queue.get(timeout=5, fail=True), timeout=6)
        body = json.loads(received.body)
        assert body["event_type"] == "NewDeviceLoginDetected"
        assert body["payload"]["device_fingerprint_hash"] == "fp-hash"
        await received.ack()
    finally:
        await connection.close()
