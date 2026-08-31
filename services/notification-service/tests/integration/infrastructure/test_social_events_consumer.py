"""SocialEventsConsumer -- against a real (testcontainers) RabbitMQ:
publishing a fixture `UserFollowed` event results in exactly one push
dispatch attempt to the followee; the same event_id redelivered results in
exactly one dispatch (idempotency, test-plan section 6); a followee who has
opted out of the `new_follower` category gets zero dispatch attempts
(suppressibility actually suppresses); a handler that raises is retried up
to the configured limit, then dead-lettered. Mirrors
test_diary_events_consumer.py's/test_identity_events_consumer.py's shape.

The seeded preference uses a deliberately narrow (1-minute) quiet-hours
window rather than the default 22:00-08:00 one -- SendNewFollowerPushHandler
is quiet-hours-gated (see application/commands/send_new_follower_push.py),
and this test exercises the handler against the real wall clock (no
injected `now_fn`, unlike the unit tests), so a ~10-hour default window
would make "dispatches immediately" flaky for roughly 40% of the day.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import time
from pathlib import Path

import aio_pika
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.entities.notification_preference import NotificationPreference
from domain.value_objects.notification_category import NotificationCategory
from domain.value_objects.quiet_hours_window import QuietHoursWindow
from infrastructure.messaging.social_events_consumer import (
    BINDING_ROUTING_KEY,
    DLQ_NAME,
    EXCHANGE_NAME,
    SocialEventsConsumer,
)
from infrastructure.persistence.models import PendingPushDispatchModel
from infrastructure.persistence.postgres_preferences_repository import (
    PostgresPreferencesRepository,
)
from tests.fixtures.factories import FakePushProviderPort, FakeTemplateRendererPort

# A quiet-hours window that is "quiet" for only one minute a day -- narrow
# enough that a spurious hit is astronomically unlikely, without needing to
# inject a fixed clock into a real-RabbitMQ-backed consumer test.
_ALWAYS_OPEN_QUIET_HOURS = QuietHoursWindow(start=time(0, 0), end=time(0, 1), tz="UTC")

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "social_events"
FOLLOWEE_ID = uuid.UUID("22222222-2222-2222-2222-222222222225")


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


async def _seed_opted_in_preference(session_factory, user_id: uuid.UUID = FOLLOWEE_ID) -> None:
    async with session_factory() as session:
        repo = PostgresPreferencesRepository(session)
        await repo.upsert(
            NotificationPreference(
                user_id=user_id,
                category=NotificationCategory.push("new_follower"),
                push_enabled=True,
                quiet_hours=_ALWAYS_OPEN_QUIET_HOURS,
            )
        )
        await session.commit()


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


async def test_user_followed_dispatches_exactly_one_push(amqp_url, session_factory):
    await _seed_opted_in_preference(session_factory)
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        push_provider = FakePushProviderPort()
        consumer = SocialEventsConsumer(session_factory, push_provider, FakeTemplateRendererPort())
        await consumer.setup(connection)
        await consumer.consume()

        await _publish(connection, "social.follow.followed", _load_fixture("user_followed.json"))

        for _ in range(20):
            if len(push_provider.calls) >= 1:
                break
            await asyncio.sleep(0.25)
        await asyncio.sleep(0.5)
        assert len(push_provider.calls) == 1
        assert push_provider.calls[0]["device_token"] == str(FOLLOWEE_ID)
    finally:
        await connection.close()


async def test_redelivering_the_same_event_dispatches_exactly_once(amqp_url, session_factory):
    await _seed_opted_in_preference(session_factory)
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        push_provider = FakePushProviderPort()
        consumer = SocialEventsConsumer(session_factory, push_provider, FakeTemplateRendererPort())
        await consumer.setup(connection)
        await consumer.consume()

        body = _load_fixture("user_followed.json")
        await _publish(connection, "social.follow.followed", body)
        await _publish(connection, "social.follow.followed", body)

        for _ in range(20):
            if len(push_provider.calls) >= 1:
                break
            await asyncio.sleep(0.25)
        await asyncio.sleep(0.5)  # let a possible second delivery finish processing
        assert len(push_provider.calls) == 1
    finally:
        await connection.close()


async def test_opted_out_followee_receives_no_dispatch_attempt(amqp_url, session_factory):
    # Deliberately not seeding an opted-in preference row -- opt-in only
    # (module docstring of send_new_follower_push.py): no explicit
    # preference row must behave identically to an explicit opt-out.
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        push_provider = FakePushProviderPort()
        consumer = SocialEventsConsumer(session_factory, push_provider, FakeTemplateRendererPort())
        await consumer.setup(connection)
        await consumer.consume()

        await _publish(connection, "social.follow.followed", _load_fixture("user_followed.json"))
        await asyncio.sleep(1.0)

        assert push_provider.calls == []
    finally:
        await connection.close()


async def test_user_followed_during_quiet_hours_persists_pending_row_not_a_dispatch(
    amqp_url, session_factory
):
    # Quiet almost the entire day (23h59m) -- deterministically "in quiet
    # hours" right now without needing to inject a fixed clock into this
    # real-RabbitMQ-backed consumer.
    always_quiet = QuietHoursWindow(start=time(0, 0), end=time(23, 59), tz="UTC")
    async with session_factory() as session:
        repo = PostgresPreferencesRepository(session)
        await repo.upsert(
            NotificationPreference(
                user_id=FOLLOWEE_ID,
                category=NotificationCategory.push("new_follower"),
                push_enabled=True,
                quiet_hours=always_quiet,
            )
        )
        await session.commit()

    connection = await aio_pika.connect_robust(amqp_url)
    try:
        push_provider = FakePushProviderPort()
        consumer = SocialEventsConsumer(session_factory, push_provider, FakeTemplateRendererPort())
        await consumer.setup(connection)
        await consumer.consume()

        await _publish(connection, "social.follow.followed", _load_fixture("user_followed.json"))
        await asyncio.sleep(1.0)

        assert push_provider.calls == []

        async with session_factory() as session:
            result = await session.execute(
                select(PendingPushDispatchModel).where(
                    PendingPushDispatchModel.user_id == FOLLOWEE_ID
                )
            )
            rows = result.scalars().all()
            assert len(rows) == 1
            assert rows[0].status == "pending"
    finally:
        await connection.close()


async def test_a_message_that_always_fails_is_dead_lettered_after_max_attempts(
    amqp_url, session_factory
):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = SocialEventsConsumer(
            session_factory, FakePushProviderPort(), FakeTemplateRendererPort(), max_attempts=1
        )
        await consumer.setup(connection)
        await consumer.consume()

        malformed_body = b"not valid json, will always raise while parsing"
        await _publish(
            connection, BINDING_ROUTING_KEY.replace("#", "follow.followed"), malformed_body
        )

        dlq_channel = await connection.channel()
        dlq = await dlq_channel.declare_queue(DLQ_NAME, durable=True)

        received = await asyncio.wait_for(dlq.get(timeout=10, fail=True), timeout=11)
        assert received.body == malformed_body
        await received.ack()
    finally:
        await connection.close()
