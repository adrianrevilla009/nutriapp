"""Asserts the FastAPI app assembled by infrastructure/main.py exposes the
expected routes (composition-level smoke test). The generic `/metrics`
Prometheus-endpoint wiring is identical boilerplate across every service
(same three-line handler, same `prometheus_client` call) -- not
re-verified per-service here; it carries no activity-service-specific
behavior."""

from __future__ import annotations

import pytest
from testcontainers.rabbitmq import RabbitMqContainer

from infrastructure.main import create_app, lifespan


def test_create_app_registers_all_expected_routes():
    app = create_app()
    schema = app.openapi()
    paths = set(schema["paths"].keys())
    assert "/api/v1/activity/exercises" in paths
    assert "/api/v1/activity/exercises/{entry_id}" in paths
    assert "/health/live" in paths
    assert "/health/ready" in paths


async def test_lifespan_starts_and_stops_the_real_container(db_engine, postgres_async_url):
    with RabbitMqContainer("rabbitmq:3.13-management-alpine") as rabbitmq_c:
        host = rabbitmq_c.get_container_host_ip()
        port = rabbitmq_c.get_exposed_port(5672)
        rabbitmq_url = f"amqp://guest:guest@{host}:{port}/"

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setenv("ACTIVITY_SERVICE_DATABASE_URL", postgres_async_url)
        monkeypatch.setenv("ACTIVITY_SERVICE_RABBITMQ_URL", rabbitmq_url)
        try:
            app = create_app()
            async with lifespan(app):
                assert app.state.container is not None
                assert app.state.container.event_publisher is not None
        finally:
            monkeypatch.undo()
