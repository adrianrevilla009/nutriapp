"""FastAPI application entrypoint. Wires the composition root and routes
(messaging-conventions SKILL.md, observability-audit SKILL.md). The
outbox relay worker runs as a separate process/task
(infrastructure/messaging/outbox_relay_worker.py), not inline here, same
convention as identity-service.
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
from infrastructure.http.routes.product_routes import router as product_router
from infrastructure.http.routes.search_routes import router as search_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container = Container(Settings.from_env())
    await container.startup()
    app.state.container = container
    logger.info("catalog_service_started")
    try:
        yield
    finally:
        await container.shutdown()
        logger.info("catalog_service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="catalog-service",
        version="0.1.0",
        description="NutriApp catalog-service: supermarket product inventory "
        "aggregation, normalization, deduplication, and full-text/faceted search.",
        lifespan=lifespan,
    )
    app.include_router(search_router)
    app.include_router(product_router)
    app.include_router(health_router)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
