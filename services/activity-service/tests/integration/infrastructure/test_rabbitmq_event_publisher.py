"""RabbitMqEventPublisher: publishes to the correct exchange/routing key
per messaging-conventions SKILL.md naming, consumable by a test
subscriber, and matches docs/events-catalog.md's documented payload
shape (test-plan section 2)."""

from __future__ import annotations

import asyncio
import json

import aio_pika
import pytest
from testcontainers.rabbitmq import RabbitMqContainer

from domain.events.exercise_logged import build_exercise_logged_event
from infrastructure.messaging.rabbitmq_event_publisher import (
    EXCHANGE_NAME,
    RabbitMqEventPublisher,
    routing_key_for,
)
from tests.fixtures.factories import make_exercise_entry


@pytest.fixture(scope="module")
def rabbitmq_container():
    with RabbitMqContainer("rabbitmq:3.13-management-alpine") as container:
        yield container


@pytest.fixture
async def amqp_url(rabbitmq_container):
    host = rabbitmq_container.get_container_host_ip()
    port = rabbitmq_container.get_exposed_port(5672)
    return f"amqp://guest:guest@{host}:{port}/"


async def test_publishes_exercise_logged_to_correct_exchange_and_routing_key(amqp_url):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        publisher = await RabbitMqEventPublisher.create(connection)

        consumer_channel = await connection.channel()
        exchange = await consumer_channel.declare_exchange(
            EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )
        queue = await consumer_channel.declare_queue(exclusive=True)
        routing_key = routing_key_for("ExerciseLogged")
        assert routing_key == "activity.exercise.logged"
        await queue.bind(exchange, routing_key=routing_key)

        entry = make_exercise_entry(duration_minutes=30, calories_burned_kcal=250.0)
        event = build_exercise_logged_event(entry=entry, correlation_id="corr-1")
        await publisher.publish(event)

        received = await asyncio.wait_for(queue.get(timeout=5, fail=True), timeout=6)
        body = json.loads(received.body)
        assert body["event_type"] == "ExerciseLogged"
        assert body["payload"]["entry_id"] == str(entry.entry_id)
        assert body["payload"]["duration_minutes"] == 30
        assert body["payload"]["calories_burned_kcal"] == 250.0
        assert set(body["payload"].keys()) == {
            "entry_id",
            "exercise_type",
            "duration_minutes",
            "calories_burned_kcal",
            "occurred_at",
            "label",
        }
        await received.ack()
    finally:
        await connection.close()
