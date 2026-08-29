"""RevocationScanWorker -- real Postgres (testcontainers) plus a real
RabbitMQ exchange (testcontainers) via a subsequent
OutboxRelayWorker.relay_once() call (the scan worker itself only enqueues
to the outbox -- publishing is OutboxRelayWorker's job, same separation of
concerns as every other service). A due row is processed and its
EntitlementRevoked event actually lands on the real exchange; a not-due
row is left alone across multiple scan cycles (test-plan section 2)."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone

import aio_pika
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from testcontainers.rabbitmq import RabbitMqContainer

from infrastructure.messaging.outbox_relay_worker import OutboxRelayWorker
from infrastructure.messaging.rabbitmq_event_publisher import (
    EXCHANGE_NAME,
    RabbitMqEventPublisher,
    routing_key_for,
)
from infrastructure.persistence.postgres_entitlement_revocation_schedule_repository import (
    PostgresEntitlementRevocationScheduleRepository,
)
from infrastructure.scheduling.revocation_scan_worker import RevocationScanWorker

pytestmark = pytest.mark.usefixtures("db_engine")

NOW = datetime.now(timezone.utc)


@pytest.fixture(scope="module")
def rabbitmq_container():
    with RabbitMqContainer("rabbitmq:3.13-management-alpine") as container:
        yield container


@pytest.fixture
async def amqp_url(rabbitmq_container):
    host = rabbitmq_container.get_container_host_ip()
    port = rabbitmq_container.get_exposed_port(5672)
    return f"amqp://guest:guest@{host}:{port}/"


async def test_due_row_is_processed_and_published_to_real_exchange(db_engine, amqp_url):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    due_user = uuid.uuid4()

    async with session_factory() as session:
        repo = PostgresEntitlementRevocationScheduleRepository(session)
        await repo.upsert_pending(due_user, NOW - timedelta(hours=1))
        await session.commit()

    worker = RevocationScanWorker(session_factory)
    processed_count = await worker.scan_once()
    assert processed_count == 1

    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer_channel = await connection.channel()
        exchange = await consumer_channel.declare_exchange(
            EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )
        queue = await consumer_channel.declare_queue(exclusive=True)
        await queue.bind(exchange, routing_key=routing_key_for("EntitlementRevoked"))

        publisher = await RabbitMqEventPublisher.create(connection)
        relay = OutboxRelayWorker(session_factory, publisher)
        relayed_count = await relay.relay_once()
        assert relayed_count == 1

        received = await asyncio.wait_for(queue.get(timeout=5, fail=True), timeout=6)
        body = json.loads(received.body)
        assert body["event_type"] == "EntitlementRevoked"
        assert body["payload"]["user_id"] == str(due_user)
        await received.ack()
    finally:
        await connection.close()

    async with session_factory() as session:
        repo = PostgresEntitlementRevocationScheduleRepository(session)
        due_again = await repo.list_due(NOW + timedelta(days=1))
    assert due_again == []


async def test_not_due_row_left_alone_across_multiple_scan_cycles(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    future_user = uuid.uuid4()

    async with session_factory() as session:
        repo = PostgresEntitlementRevocationScheduleRepository(session)
        await repo.upsert_pending(future_user, NOW + timedelta(days=30))
        await session.commit()

    worker = RevocationScanWorker(session_factory)
    assert await worker.scan_once() == 0
    assert await worker.scan_once() == 0
    assert await worker.scan_once() == 0
