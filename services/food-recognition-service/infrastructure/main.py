"""FastAPI application entrypoint. Wires the composition root and routes
(messaging-conventions SKILL.md, observability-audit SKILL.md). The
outbox relay worker runs as a background task started from
Container.startup(), not inline here, same convention as every other
service.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from infrastructure.composition_root import Container, Settings
from infrastructure.http.health import router as health_router
from infrastructure.http.routes.recognition_routes import router as recognition_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container = Container(Settings.from_env())
    await container.startup()
    app.state.container = container
    logger.info("food_recognition_service_started")
    try:
        yield
    finally:
        await container.shutdown()
        logger.info("food_recognition_service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="food-recognition-service",
        version="0.1.0",
        description="NutriApp food-recognition-service: photo-based AI food detection "
        "(Claude vision) and barcode-based product detection, pending diary-service "
        "confirmation.",
        lifespan=lifespan,
    )
    app.include_router(recognition_router)
    app.include_router(health_router)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
