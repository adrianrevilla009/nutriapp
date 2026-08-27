"""RabbitMqEventPublisher: publishes to the correct exchange/routing key
per messaging-conventions SKILL.md naming, consumable by a test subscriber.
"""

from __future__ import annotations

import asyncio
import json

import aio_pika
import pytest
from testcontainers.rabbitmq import RabbitMqContainer

from domain.entities.product import Product
from domain.events.product_catalogued import build_product_catalogued_event
from infrastructure.messaging.rabbitmq_event_publisher import (
    EXCHANGE_NAME,
    RabbitMqEventPublisher,
    routing_key_for,
)
from tests.fixtures.factories import make_raw_record


@pytest.fixture(scope="module")
def rabbitmq_container():
    with RabbitMqContainer("rabbitmq:3.13-management-alpine") as container:
        yield container


@pytest.fixture
async def amqp_url(rabbitmq_container):
    host = rabbitmq_container.get_container_host_ip()
    port = rabbitmq_container.get_exposed_port(5672)
    return f"amqp://guest:guest@{host}:{port}/"


async def test_publishes_product_catalogued_to_correct_exchange_and_routing_key(amqp_url):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        publisher = await RabbitMqEventPublisher.create(connection)

        consumer_channel = await connection.channel()
        exchange = await consumer_channel.declare_exchange(
            EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )
        queue = await consumer_channel.declare_queue(exclusive=True)
        routing_key = routing_key_for("ProductCatalogued")
        assert routing_key == "catalog.product.catalogued"
        await queue.bind(exchange, routing_key=routing_key)

        product = Product.merge(existing=None, incoming=make_raw_record()).product
        event = build_product_catalogued_event(product=product, correlation_id="corr-1")
        await publisher.publish(event)

        received = await asyncio.wait_for(queue.get(timeout=5, fail=True), timeout=6)
        body = json.loads(received.body)
        assert body["event_type"] == "ProductCatalogued"
        assert body["payload"]["product_id"] == str(product.product_id)
        await received.ack()
    finally:
        await connection.close()
