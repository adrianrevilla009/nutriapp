"""RabbitMqEventPublisher: publishes to the correct exchange/routing key
per messaging-conventions SKILL.md naming, consumable by a test
subscriber."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

import aio_pika
import pytest
from testcontainers.rabbitmq import RabbitMqContainer

from domain.events.food_photo_analyzed import build_food_photo_analyzed_event
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


async def test_publishes_food_photo_analyzed_to_correct_exchange_and_routing_key(amqp_url):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        publisher = await RabbitMqEventPublisher.create(connection)

        consumer_channel = await connection.channel()
        exchange = await consumer_channel.declare_exchange(
            EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )
        queue = await consumer_channel.declare_queue(exclusive=True)
        routing_key = routing_key_for("FoodPhotoAnalyzed")
        assert routing_key == "food-recognition.photo.analyzed"
        await queue.bind(exchange, routing_key=routing_key)

        analysis_id = uuid.uuid4()
        event = build_food_photo_analyzed_event(
            analysis_id=analysis_id,
            user_id=uuid.uuid4(),
            candidates=[],
            model_version="claude-haiku-4-5",
            status="unavailable",
            correlation_id="corr-1",
            occurred_at=datetime.now(timezone.utc),
        )
        await publisher.publish(event)

        received = await asyncio.wait_for(queue.get(timeout=5, fail=True), timeout=6)
        body = json.loads(received.body)
        assert body["event_type"] == "FoodPhotoAnalyzed"
        assert body["payload"]["analysis_id"] == str(analysis_id)
        await received.ack()
    finally:
        await connection.close()
