"""RabbitMqEventPublisher -- against a real (testcontainers) RabbitMQ:
publishing routes to the correct routing key on the `social.events`
exchange, and the published body round-trips via `to_wire()`."""

from __future__ import annotations

import json

import aio_pika
import pytest

from domain.events.user_followed import build_user_followed_event
from infrastructure.messaging.rabbitmq_event_publisher import EXCHANGE_NAME, RabbitMqEventPublisher
from tests.fixtures.factories import NOW, make_follow


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


async def test_publish_routes_to_expected_key_and_body_round_trips(amqp_url):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        publisher = await RabbitMqEventPublisher.create(connection)

        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )
        queue = await channel.declare_queue("test-social-follow-followed", durable=False)
        await queue.bind(exchange, routing_key="social.follow.followed")

        follow = make_follow()
        event = build_user_followed_event(
            follow_id=follow.follow_id,
            follower_id=follow.follower_id,
            followee_id=follow.followee_id,
            followed_at=NOW,
            correlation_id="corr-1",
        )
        await publisher.publish(event)

        message = await queue.get(timeout=10, fail=True)
        body = json.loads(message.body.decode("utf-8"))
        assert body["event_type"] == "UserFollowed"
        assert body["payload"]["follow_id"] == str(follow.follow_id)
        await message.ack()
    finally:
        await connection.close()
