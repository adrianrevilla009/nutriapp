"""Fixtures shared by this service's two topic-consumer integration
suites (`test_billing_events_consumer.py`, `test_recipe_events_consumer.py`)
-- both need a real (testcontainers) RabbitMQ and a session factory over
the module's `db_engine`, so that setup lives here once instead of being
duplicated per test module. `rabbitmq_container` stays module-scoped: each
test module (billing vs. recipe) still gets its own container instance,
pytest's fixture caching is keyed by the requesting module either way."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker


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
