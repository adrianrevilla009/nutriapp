"""Asserts the FastAPI app assembled by infrastructure/main.py exposes the
expected routes and that its lifespan starts/stops a real Container
cleanly (composition-level smoke test). No testcontainers needed
(unlike every other service): this service has no database and no
message broker."""

from __future__ import annotations

import httpx

from infrastructure.main import create_app, lifespan


def test_create_app_registers_all_expected_routes():
    app = create_app()
    schema = app.openapi()
    paths = set(schema["paths"].keys())
    assert "/api/v1/bff/dashboard" in paths
    assert "/health/live" in paths
    assert "/health/ready" in paths


async def test_metrics_endpoint_returns_prometheus_content_type():
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


async def test_lifespan_starts_and_stops_the_real_container(monkeypatch):
    monkeypatch.setenv("BFF_SERVICE_DIARY_SERVICE_BASE_URL", "http://diary-service.test:8000")
    monkeypatch.setenv(
        "BFF_SERVICE_NUTRITION_CALCULATION_SERVICE_BASE_URL",
        "http://nutrition-calculation-service.test:8000",
    )

    app = create_app()
    async with lifespan(app):
        assert app.state.container is not None
        assert app.state.container.diary_summary_client is not None
        assert app.state.container.nutrition_calculation_client is not None
