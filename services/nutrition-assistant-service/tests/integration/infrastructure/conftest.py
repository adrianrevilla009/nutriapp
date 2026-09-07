"""Additional testcontainers fixtures (RabbitMQ, Qdrant) + session_factory,
layered on top of the root tests/conftest.py's Postgres db_engine
fixture."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker


@pytest.fixture
def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


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


@pytest.fixture(scope="module")
def qdrant_container():
    from testcontainers.core.container import DockerContainer
    from testcontainers.core.waiting_utils import wait_for_logs

    container = DockerContainer("qdrant/qdrant:v1.11.3").with_exposed_ports(6333)
    container.start()
    wait_for_logs(container, "Actix runtime found", timeout=30)
    try:
        yield container
    finally:
        container.stop()


@pytest.fixture
def qdrant_url(qdrant_container) -> str:
    host = qdrant_container.get_container_host_ip()
    port = qdrant_container.get_exposed_port(6333)
    return f"http://{host}:{port}"
