"""RecipeEventsConsumer -- same idempotency/DLQ shape as
test_billing_events_consumer.py, independently, against
`RecipePublished`/`RecipeUnpublished` fixture events (never a real call to
recipe-service, test-plan section 2)."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aio_pika
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from infrastructure.messaging.recipe_events_consumer import (
    BINDING_ROUTING_KEY,
    DLQ_NAME,
    EXCHANGE_NAME,
    RecipeEventsConsumer,
)
from infrastructure.persistence.postgres_feed_repository import PostgresFeedRepository

FIXTURES_DIR = Path(__file__).parents[2] / "fixtures" / "recipe_events"


def _load_fixture_payload(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


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


def _recipe_published_body(recipe_id: uuid.UUID, user_id: uuid.UUID, event_id: uuid.UUID) -> bytes:
    # Fixture payload (test-plan section 8) as the template shape; recipe_id/
    # user_id are substituted per-test so the idempotency assertions below
    # can target a unique, freshly-generated recipe/author pair.
    payload = _load_fixture_payload("recipe_published_payload.json")
    payload["recipe_id"] = str(recipe_id)
    payload["user_id"] = str(user_id)
    body = {
        "event_id": str(event_id),
        "aggregate_id": str(recipe_id),
        "event_type": "RecipePublished",
        "version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
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


async def test_redelivering_the_same_recipe_published_event_upserts_feed_exactly_once(
    amqp_url, session_factory
):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = RecipeEventsConsumer(session_factory)
        await consumer.setup(connection)
        await consumer.consume()

        recipe_id = uuid.uuid4()
        user_id = uuid.uuid4()
        event_id = uuid.uuid4()
        body = _recipe_published_body(recipe_id, user_id, event_id)

        await _publish(connection, "recipe.recipe.published", body)
        await _publish(connection, "recipe.recipe.published", body)

        entry = None
        for _ in range(20):
            async with session_factory() as session:
                feed = PostgresFeedRepository(session)
                results = await feed.list_for_authors([user_id])
            if results:
                entry = results[0]
                break
            await asyncio.sleep(0.25)
        await asyncio.sleep(0.5)  # let a possible second delivery finish processing

        assert entry is not None
        assert entry.recipe_id == recipe_id
    finally:
        await connection.close()


async def test_a_message_that_always_fails_is_dead_lettered_after_max_attempts(
    amqp_url, session_factory
):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = RecipeEventsConsumer(session_factory, max_attempts=1)
        await consumer.setup(connection)
        await consumer.consume()

        malformed_body = b"not valid json, will always raise while parsing"
        await _publish(connection, BINDING_ROUTING_KEY.replace("*", "published"), malformed_body)

        dlq_channel = await connection.channel()
        dlq = await dlq_channel.declare_queue(DLQ_NAME, durable=True)

        received = await asyncio.wait_for(dlq.get(timeout=10, fail=True), timeout=11)
        assert received.body == malformed_body
        await received.ack()
    finally:
        await connection.close()
