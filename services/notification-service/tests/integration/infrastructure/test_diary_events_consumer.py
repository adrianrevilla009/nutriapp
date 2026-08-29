"""DiaryEventsConsumer -- against a real (testcontainers) RabbitMQ:
publishing the same event twice results in exactly one projection effect
(test-plan section 2's mandatory idempotency test); a handler that raises
is retried up to the configured limit, then dead-lettered."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

import aio_pika
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from infrastructure.messaging.diary_events_consumer import (
    BINDING_ROUTING_KEY,
    DLQ_NAME,
    EXCHANGE_NAME,
    DiaryEventsConsumer,
)
from infrastructure.persistence.models import ReminderScheduleModel

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "diary_events"


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


async def test_fasting_window_started_is_projected(amqp_url, session_factory):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = DiaryEventsConsumer(session_factory)
        await consumer.setup(connection)
        await consumer.consume()

        await _publish(
            connection, "diary.fasting_window.started", _load_fixture("fasting_window_started.json")
        )
        window_id = uuid.UUID("66666666-6666-6666-6666-666666666661")

        async def _projected() -> bool:
            async with session_factory() as session:
                result = await session.execute(
                    select(ReminderScheduleModel).where(
                        ReminderScheduleModel.source_aggregate_id == str(window_id)
                    )
                )
                return result.scalar_one_or_none() is not None

        for _ in range(20):
            if await _projected():
                break
            await asyncio.sleep(0.25)
        assert await _projected()
    finally:
        await connection.close()


async def test_redelivering_the_same_event_does_not_double_project(amqp_url, session_factory):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = DiaryEventsConsumer(session_factory)
        await consumer.setup(connection)
        await consumer.consume()

        body = _load_fixture("meal_planned.json")
        await _publish(connection, "diary.meal_plan.planned", body)
        await _publish(connection, "diary.meal_plan.planned", body)

        plan_entry_id = uuid.UUID("99999999-9999-9999-9999-999999999991")

        async def _row_count() -> int:
            async with session_factory() as session:
                result = await session.execute(
                    select(ReminderScheduleModel).where(
                        ReminderScheduleModel.source_aggregate_id == str(plan_entry_id)
                    )
                )
                return len(list(result.scalars()))

        for _ in range(20):
            if await _row_count() >= 1:
                break
            await asyncio.sleep(0.25)
        await asyncio.sleep(0.5)
        assert await _row_count() == 1
    finally:
        await connection.close()


async def test_water_intake_logged_is_acked_and_creates_no_row(amqp_url, session_factory):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = DiaryEventsConsumer(session_factory)
        await consumer.setup(connection)
        await consumer.consume()

        await _publish(
            connection, "diary.water_intake.logged", _load_fixture("water_intake_logged.json")
        )
        await asyncio.sleep(1.0)

        async with session_factory() as session:
            result = await session.execute(select(ReminderScheduleModel))
            assert list(result.scalars()) == []
    finally:
        await connection.close()


async def test_water_intake_removed_is_acked_and_creates_no_row(amqp_url, session_factory):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = DiaryEventsConsumer(session_factory)
        await consumer.setup(connection)
        await consumer.consume()

        await _publish(
            connection, "diary.water_intake.removed", _load_fixture("water_intake_removed.json")
        )
        await asyncio.sleep(1.0)

        async with session_factory() as session:
            result = await session.execute(select(ReminderScheduleModel))
            assert list(result.scalars()) == []
    finally:
        await connection.close()


async def test_fasting_window_ended_dispatch_removes_the_matching_row(amqp_url, session_factory):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = DiaryEventsConsumer(session_factory)
        await consumer.setup(connection)
        await consumer.consume()

        window_id = uuid.UUID("66666666-6666-6666-6666-666666666661")

        await _publish(
            connection, "diary.fasting_window.started", _load_fixture("fasting_window_started.json")
        )

        async def _row_exists() -> bool:
            async with session_factory() as session:
                result = await session.execute(
                    select(ReminderScheduleModel).where(
                        ReminderScheduleModel.source_aggregate_id == str(window_id)
                    )
                )
                return result.scalar_one_or_none() is not None

        for _ in range(20):
            if await _row_exists():
                break
            await asyncio.sleep(0.25)
        assert await _row_exists()

        await _publish(
            connection, "diary.fasting_window.ended", _load_fixture("fasting_window_ended.json")
        )

        for _ in range(20):
            if not await _row_exists():
                break
            await asyncio.sleep(0.25)
        assert not await _row_exists()
    finally:
        await connection.close()


async def test_meal_plan_updated_dispatch_updates_the_row_in_place(amqp_url, session_factory):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = DiaryEventsConsumer(session_factory)
        await consumer.setup(connection)
        await consumer.consume()

        plan_entry_id = uuid.UUID("99999999-9999-9999-9999-999999999991")

        await _publish(connection, "diary.meal_plan.planned", _load_fixture("meal_planned.json"))

        async def _get_row():
            async with session_factory() as session:
                result = await session.execute(
                    select(ReminderScheduleModel).where(
                        ReminderScheduleModel.source_aggregate_id == str(plan_entry_id)
                    )
                )
                return result.scalar_one_or_none()

        for _ in range(20):
            if await _get_row() is not None:
                break
            await asyncio.sleep(0.25)
        original_row = await _get_row()
        assert original_row is not None
        original_schedule_id = original_row.schedule_id
        original_due_at = original_row.due_at

        await _publish(
            connection, "diary.meal_plan.updated", _load_fixture("meal_plan_updated.json")
        )

        async def _updated() -> bool:
            row = await _get_row()
            return row is not None and row.due_at != original_due_at

        for _ in range(20):
            if await _updated():
                break
            await asyncio.sleep(0.25)
        assert await _updated()

        updated_row = await _get_row()
        # Dispatched to handle_meal_plan_updated, not re-created via
        # handle_meal_planned: same schedule_id, never a duplicate row.
        assert updated_row.schedule_id == original_schedule_id

        async with session_factory() as session:
            result = await session.execute(
                select(ReminderScheduleModel).where(
                    ReminderScheduleModel.source_aggregate_id == str(plan_entry_id)
                )
            )
            assert len(list(result.scalars())) == 1
    finally:
        await connection.close()


async def test_meal_plan_removed_dispatch_removes_the_row(amqp_url, session_factory):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = DiaryEventsConsumer(session_factory)
        await consumer.setup(connection)
        await consumer.consume()

        plan_entry_id = uuid.UUID("99999999-9999-9999-9999-999999999991")

        await _publish(connection, "diary.meal_plan.planned", _load_fixture("meal_planned.json"))

        async def _row_exists() -> bool:
            async with session_factory() as session:
                result = await session.execute(
                    select(ReminderScheduleModel).where(
                        ReminderScheduleModel.source_aggregate_id == str(plan_entry_id)
                    )
                )
                return result.scalar_one_or_none() is not None

        for _ in range(20):
            if await _row_exists():
                break
            await asyncio.sleep(0.25)
        assert await _row_exists()

        await _publish(
            connection, "diary.meal_plan.removed", _load_fixture("meal_plan_removed.json")
        )

        for _ in range(20):
            if not await _row_exists():
                break
            await asyncio.sleep(0.25)
        assert not await _row_exists()
    finally:
        await connection.close()


async def test_a_message_that_always_fails_is_dead_lettered_after_max_attempts(
    amqp_url, session_factory
):
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        consumer = DiaryEventsConsumer(session_factory, max_attempts=1)
        await consumer.setup(connection)
        await consumer.consume()

        malformed_body = b"not valid json, will always raise while parsing"
        await _publish(
            connection, BINDING_ROUTING_KEY.replace("#", "fasting_window.started"), malformed_body
        )

        dlq_channel = await connection.channel()
        dlq = await dlq_channel.declare_queue(DLQ_NAME, durable=True)

        received = await asyncio.wait_for(dlq.get(timeout=10, fail=True), timeout=11)
        assert received.body == malformed_body
        await received.ack()
    finally:
        await connection.close()
