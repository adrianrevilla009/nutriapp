"""FastAPI application entrypoint. Wires the composition root and routes
(messaging-conventions SKILL.md, observability-audit SKILL.md). Both
message consumers and the outbox relay worker run as background tasks
started from Container.startup(), mirroring recipe-service's/
notification-service's precedent."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from infrastructure.composition_root import Container, Settings
from infrastructure.http.health import router as health_router
from infrastructure.http.routes.feed_routes import router as feed_router
from infrastructure.http.routes.follow_routes import router as follow_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container = Container(Settings.from_env())
    await container.startup()
    app.state.container = container
    logger.info("social_service_started")
    try:
        yield
    finally:
        await container.shutdown()
        logger.info("social_service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="social-service",
        version="0.1.0",
        description="NutriApp social-service: one-way follow connections between users and a "
        "Pro-gated activity feed composed from followed users' published recipes "
        "(CLAUDE.md section 2.2).",
        lifespan=lifespan,
    )
    app.include_router(follow_router)
    app.include_router(feed_router)
    app.include_router(health_router)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
