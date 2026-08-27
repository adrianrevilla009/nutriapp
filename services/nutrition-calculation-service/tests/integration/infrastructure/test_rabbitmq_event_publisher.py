"""RabbitMqEventPublisher: publishes to the correct exchange/routing key
per messaging-conventions SKILL.md naming, consumable by a test
subscriber."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import date, datetime, timezone

import aio_pika
import pytest
from testcontainers.rabbitmq import RabbitMqContainer

from domain.entities.daily_nutrition_total import DailyNutritionTotal
from domain.events.nutrition_value_recomputed import build_nutrition_value_recomputed_event
from domain.value_objects.formula_version import CURRENT_FORMULA_VERSION
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


async def test_publishes_nutrition_value_recomputed_to_correct_exchange_and_routing_key(amqp_url):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        publisher = await RabbitMqEventPublisher.create(connection)

        consumer_channel = await connection.channel()
        exchange = await consumer_channel.declare_exchange(
            EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )
        queue = await consumer_channel.declare_queue(exclusive=True)
        routing_key = routing_key_for("NutritionValueRecomputed")
        assert routing_key == "nutrition-calculation.total.recomputed"
        await queue.bind(exchange, routing_key=routing_key)

        user_id = uuid.uuid4()
        line = DailyNutritionTotal(user_id=user_id, total_date=date(2026, 8, 25)).compute_total()
        event = build_nutrition_value_recomputed_event(
            user_id=user_id,
            scope="day",
            entry_id=None,
            total_date=date(2026, 8, 25),
            line=line,
            confidence_range=None,
            formula_version=CURRENT_FORMULA_VERSION,
            reason="food_entry_logged",
            correlation_id="corr-1",
            recomputed_at=datetime.now(timezone.utc),
        )
        await publisher.publish(event)

        received = await asyncio.wait_for(queue.get(timeout=5, fail=True), timeout=6)
        body = json.loads(received.body)
        assert body["event_type"] == "NutritionValueRecomputed"
        assert body["payload"]["user_id"] == str(user_id)
        await received.ack()
    finally:
        await connection.close()
