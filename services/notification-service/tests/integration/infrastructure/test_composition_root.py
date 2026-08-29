"""Proves Settings.from_env() and the real Container wiring work end-to-end
against real Postgres/RabbitMQ (testcontainers) -- exercising
Container.__init__/startup()/shutdown() itself so a wiring typo doesn't go
undetected (identity-service's test_composition_root.py precedent)."""

from __future__ import annotations

import pytest
from testcontainers.rabbitmq import RabbitMqContainer

from infrastructure.composition_root import Container, Settings


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
    monkeypatch.setenv("NOTIFICATION_SERVICE_DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("NOTIFICATION_SERVICE_IDENTITY_REVEAL_CREDENTIAL", "secret")
    monkeypatch.setenv("NOTIFICATION_SERVICE_REMINDER_SCAN_INTERVAL_SECONDS", "30")

    settings = Settings.from_env()

    assert settings.database_url == "postgresql+asyncpg://u:p@h/db"
    assert settings.identity_reveal_credential == "secret"
    assert settings.reminder_scan_interval_seconds == 30.0
    assert settings.rabbitmq_url == "amqp://guest:guest@localhost/"
    assert settings.identity_issuer == "identity-service"


def test_settings_from_env_defaults_reminder_scan_interval(monkeypatch):
    monkeypatch.setenv("NOTIFICATION_SERVICE_DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.delenv("NOTIFICATION_SERVICE_REMINDER_SCAN_INTERVAL_SECONDS", raising=False)

    settings = Settings.from_env()

    assert settings.reminder_scan_interval_seconds == 60.0


async def test_container_startup_and_shutdown_wires_both_consumers(
    postgres_async_url, rabbitmq_url
):
    settings = Settings(
        database_url=postgres_async_url,
        rabbitmq_url=rabbitmq_url,
        identity_jwks_url="http://identity-service.test/.well-known/jwks.json",
        identity_issuer="identity-service",
        identity_service_base_url="http://identity-service.test",
        identity_reveal_credential="test-credential",
        ses_base_url="http://ses-fake.test",
        ses_from_address="no-reply@nutriapp.example",
        sns_base_url="http://sns-fake.test",
        reminder_scan_interval_seconds=3600.0,
    )
    container = Container(settings)

    from infrastructure.persistence.models import Base

    async with container.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await container.startup()
    try:
        async with container.new_session() as session:
            assert session is not None
    finally:
        await container.shutdown()
        async with container.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await container.engine.dispose()
