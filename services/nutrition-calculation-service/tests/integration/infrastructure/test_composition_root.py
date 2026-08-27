"""Proves Settings.from_env() and the real Container wiring work end-to-end
against real Postgres/Redis/RabbitMQ (testcontainers) -- a gap flagged by
test-review precedent (identity-service's test_composition_root.py):
per-adapter unit/integration tests re-create their own wiring rather than
exercising Container.__init__/startup()/shutdown() itself, so a typo there
would otherwise go undetected.
"""

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
    monkeypatch.setenv(
        "NUTRITION_CALCULATION_SERVICE_DATABASE_URL", "postgresql+asyncpg://u:p@h/db"
    )
    monkeypatch.setenv("NUTRITION_CALCULATION_SERVICE_PROFILE_REVEAL_CREDENTIAL", "secret")

    settings = Settings.from_env()

    assert settings.database_url == "postgresql+asyncpg://u:p@h/db"
    assert settings.profile_reveal_credential == "secret"
    assert settings.rabbitmq_url == "amqp://guest:guest@localhost/"
    assert settings.identity_issuer == "identity-service"


async def test_container_startup_and_shutdown_wires_consumers_and_outbox_relay(
    postgres_async_url, redis_url, rabbitmq_url
):
    settings = Settings(
        database_url=postgres_async_url,
        rabbitmq_url=rabbitmq_url,
        redis_url=redis_url,
        identity_jwks_url="http://identity-service.test/.well-known/jwks.json",
        identity_issuer="identity-service",
        profile_service_base_url="http://profile-service.test",
        profile_reveal_credential="test-credential",
    )
    container = Container(settings)

    # Tables must exist for the consumers' first message (none sent here)
    # to have somewhere to write -- reuse the ORM metadata directly rather
    # than running Alembic in this test (test_migration_0001.py already
    # covers the migration itself).
    from infrastructure.persistence.models import Base

    async with container.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await container.startup()
    try:
        assert container.event_publisher is not None
        async with container.new_session() as session:
            repos = build_repositories(session)
            assert len(repos) == 5
    finally:
        await container.shutdown()
        async with container.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await container.engine.dispose()
