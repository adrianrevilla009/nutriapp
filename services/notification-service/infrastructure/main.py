"""FastAPI application entrypoint. Wires the composition root and routes
(messaging-conventions SKILL.md, observability-audit SKILL.md). The three
RabbitMQ consumers and the reminder-scan worker all run as background
tasks/consumers started from Container.startup(), not inline here, same
convention as every other service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from infrastructure.composition_root import Container, Settings
from infrastructure.http.health import router as health_router
from infrastructure.http.routes.preferences_routes import router as preferences_router
from infrastructure.http.routes.provider_webhook_routes import router as provider_webhook_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container = Container(Settings.from_env())
    await container.startup()
    app.state.container = container
    logger.info("notification_service_started")
    try:
        yield
    finally:
        await container.shutdown()
        logger.info("notification_service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="notification-service",
        version="0.1.0",
        description="NutriApp notification-service: transactional email and push "
        "notification delivery, triggered by events from other services.",
        lifespan=lifespan,
    )
    app.include_router(preferences_router)
    app.include_router(provider_webhook_router)
    app.include_router(health_router)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
