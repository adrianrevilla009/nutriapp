"""Proves Settings.from_env() and the real Container wiring work
end-to-end against real Postgres/RabbitMQ (testcontainers) -- exercising
Container.__init__/startup()/shutdown() itself so a wiring typo doesn't go
undetected (identity-service's test_composition_root.py precedent)."""

from __future__ import annotations

import pytest
from testcontainers.rabbitmq import RabbitMqContainer

from infrastructure.composition_root import Container, Settings, build_repositories


@pytest.fixture(scope="module")
def rabbitmq_container():
    with RabbitMqContainer("rabbitmq:3.13-management-alpine") as container:
        yield container


@pytest.fixture
def rabbitmq_url(rabbitmq_container) -> str:
    host = rabbitmq_container.get_container_host_ip()
    port = rabbitmq_container.get_exposed_port(5672)
    return f"amqp://guest:guest@{host}:{port}/"


def test_settings_from_env_reads_expected_variables(monkeypatch):
    monkeypatch.setenv("ACTIVITY_SERVICE_DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("ACTIVITY_SERVICE_RABBITMQ_URL", "amqp://guest:guest@rabbit/")
    monkeypatch.setenv(
        "ACTIVITY_SERVICE_IDENTITY_JWKS_URL", "http://identity.test/.well-known/jwks.json"
    )

    settings = Settings.from_env()

    assert settings.database_url == "postgresql+asyncpg://u:p@h/db"
    assert settings.rabbitmq_url == "amqp://guest:guest@rabbit/"
    assert settings.identity_jwks_url == "http://identity.test/.well-known/jwks.json"


def test_settings_from_env_defaults_rabbitmq_and_jwks_url(monkeypatch):
    monkeypatch.setenv("ACTIVITY_SERVICE_DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.delenv("ACTIVITY_SERVICE_RABBITMQ_URL", raising=False)
    monkeypatch.delenv("ACTIVITY_SERVICE_IDENTITY_JWKS_URL", raising=False)

    settings = Settings.from_env()

    assert settings.rabbitmq_url == "amqp://guest:guest@localhost/"
    assert settings.identity_jwks_url == "http://localhost:8000/.well-known/jwks.json"


async def test_container_startup_and_shutdown_wires_outbox_relay(postgres_async_url, rabbitmq_url):
    settings = Settings(
        database_url=postgres_async_url,
        rabbitmq_url=rabbitmq_url,
        identity_jwks_url="http://identity-service.test/.well-known/jwks.json",
    )
    container = Container(settings)

    from infrastructure.persistence.models import Base

    async with container.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await container.startup()
    try:
        assert container.event_publisher is not None
        async with container.new_session() as session:
            repos = build_repositories(session)
            assert len(repos) == 2
    finally:
        await container.shutdown()
        async with container.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await container.engine.dispose()


def test_event_publisher_property_raises_before_startup():
    settings = Settings(
        database_url="postgresql+asyncpg://u:p@h/db",
        rabbitmq_url="amqp://guest:guest@localhost/",
        identity_jwks_url="http://identity-service.test/.well-known/jwks.json",
    )
    container = Container(settings)
    with pytest.raises(RuntimeError):
        _ = container.event_publisher
