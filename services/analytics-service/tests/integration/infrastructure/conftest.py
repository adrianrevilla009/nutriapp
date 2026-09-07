"""Fixtures shared by this service's four topic-consumer integration
suites -- a real (testcontainers) RabbitMQ and a session factory over the
module's `db_engine`."""

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
