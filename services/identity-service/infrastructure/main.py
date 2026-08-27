"""FastAPI application entrypoint. Wires the composition root, routes, and
the outbox relay worker (observability-audit SKILL.md, messaging-
conventions SKILL.md).
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
from infrastructure.http.routes.auth_routes import router as auth_router
from infrastructure.http.routes.internal_token_routes import router as internal_router
from infrastructure.http.routes.jwks_routes import router as jwks_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container = Container(Settings.from_env())
    await container.startup()
    app.state.container = container
    logger.info("identity_service_started")
    try:
        yield
    finally:
        await container.shutdown()
        logger.info("identity_service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="identity-service",
        version="0.1.0",
        description="NutriApp identity-service: authentication, registration, "
        "session/token management, and authorization.",
        lifespan=lifespan,
    )
    app.include_router(auth_router)
    app.include_router(jwks_router)
    app.include_router(internal_router)
    app.include_router(health_router)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
