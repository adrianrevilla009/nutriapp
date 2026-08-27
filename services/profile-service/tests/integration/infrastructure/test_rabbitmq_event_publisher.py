"""RabbitMqEventPublisher: publishes to the correct exchange/routing key
per messaging-conventions SKILL.md naming, consumable by a test
subscriber (test-plan section 2)."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

import aio_pika
import pytest
from testcontainers.rabbitmq import RabbitMqContainer

from domain.events.weight_recorded import build_weight_recorded_event
from infrastructure.messaging.rabbitmq_event_publisher import (
    EXCHANGE_NAME,
    RabbitMqEventPublisher,
    routing_key_for,
)


@pytest.fixture(scope="module")
def rabbitmq_container():
    with RabbitMqContainer("rabbitmq:3.13-management-alpine") as container:
        yield container


@pytest.fixture
async def amqp_url(rabbitmq_container):
    host = rabbitmq_container.get_container_host_ip()
    port = rabbitmq_container.get_exposed_port(5672)
    return f"amqp://guest:guest@{host}:{port}/"


async def test_publishes_to_correct_exchange_and_routing_key_consumable(amqp_url):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        publisher = await RabbitMqEventPublisher.create(connection)

        consumer_channel = await connection.channel()
        exchange = await consumer_channel.declare_exchange(
            EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )
        queue = await consumer_channel.declare_queue(exclusive=True)
        routing_key = routing_key_for("WeightRecorded")
        assert routing_key == "profile.profile.weight_recorded"
        await queue.bind(exchange, routing_key=routing_key)

        event = build_weight_recorded_event(
            user_id=uuid.uuid4(),
            weight_kg=70.0,
            recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            correlation_id="corr-1",
        )
        await publisher.publish(event)

        received = await asyncio.wait_for(queue.get(timeout=5, fail=True), timeout=6)
        body = json.loads(received.body)
        assert body["event_type"] == "WeightRecorded"
        assert body["payload"]["weight_kg"] == 70.0
        await received.ack()
    finally:
        await connection.close()
