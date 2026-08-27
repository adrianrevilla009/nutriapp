"""Proves Settings.from_env() and the real Container wiring work end-to-end
against real Postgres/RabbitMQ (testcontainers) -- exercising
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
    monkeypatch.setenv("FOOD_RECOGNITION_SERVICE_DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("FOOD_RECOGNITION_SERVICE_CATALOG_LOOKUP_CREDENTIAL", "secret")
    monkeypatch.setenv("FOOD_RECOGNITION_CONFIDENCE_THRESHOLD", "0.75")
    monkeypatch.setenv("FOOD_RECOGNITION_PHOTO_ANALYSIS_ENABLED", "false")

    settings = Settings.from_env()

    assert settings.database_url == "postgresql+asyncpg://u:p@h/db"
    assert settings.catalog_lookup_credential == "secret"
    assert settings.confidence_threshold == 0.75
    assert settings.photo_analysis_enabled is False
    assert settings.rabbitmq_url == "amqp://guest:guest@localhost/"
    assert settings.identity_issuer == "identity-service"
    assert settings.vision_model == "claude-haiku-4-5"


def test_settings_from_env_defaults_photo_analysis_enabled_to_true(monkeypatch):
    monkeypatch.setenv("FOOD_RECOGNITION_SERVICE_DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.delenv("FOOD_RECOGNITION_PHOTO_ANALYSIS_ENABLED", raising=False)

    settings = Settings.from_env()

    assert settings.photo_analysis_enabled is True


async def test_container_startup_and_shutdown_wires_outbox_relay(postgres_async_url, rabbitmq_url):
    settings = Settings(
        database_url=postgres_async_url,
        rabbitmq_url=rabbitmq_url,
        identity_jwks_url="http://identity-service.test/.well-known/jwks.json",
        identity_issuer="identity-service",
        anthropic_api_key="test-key",
        vision_model="claude-haiku-4-5",
        catalog_service_base_url="http://catalog-service.test",
        catalog_lookup_credential="test-credential",
        confidence_threshold=0.6,
        photo_analysis_enabled=True,
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
            assert len(repos) == 3
    finally:
        await container.shutdown()
        async with container.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await container.engine.dispose()
