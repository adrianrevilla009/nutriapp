"""FastAPI application entrypoint. Wires the composition root and routes
(messaging-conventions SKILL.md, observability-audit SKILL.md). All four
message consumers and the outbox relay worker run as background tasks
started from Container.startup()."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from infrastructure.composition_root import Container, Settings
from infrastructure.http.health import router as health_router
from infrastructure.http.routes.report_routes import router as report_router
from infrastructure.http.routes.trend_routes import router as trend_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container = Container(Settings.from_env())
    await container.startup()
    app.state.container = container
    logger.info("analytics_service_started")
    try:
        yield
    finally:
        await container.shutdown()
        logger.info("analytics_service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="analytics-service",
        version="0.1.0",
        description="NutriApp analytics-service: CQRS read-side trend analysis, "
        "nutrient-deficiency anomaly detection, and Pro-gated CSV report/export "
        "(CLAUDE.md section 2.2, ADR-0002).",
        lifespan=lifespan,
    )
    app.include_router(trend_router)
    app.include_router(report_router)
    app.include_router(health_router)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
