"""FastAPI application entrypoint. Wires the composition root, routes, the
outbox relay worker, and the UserRegistered consumer (observability-audit
SKILL.md, messaging-conventions SKILL.md).
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
from infrastructure.http.routes.consent_routes import router as consent_router
from infrastructure.http.routes.profile_routes import router as profile_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container = Container(Settings.from_env())
    await container.startup()
    app.state.container = container
    logger.info("profile_service_started")
    try:
        yield
    finally:
        await container.shutdown()
        logger.info("profile_service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="profile-service",
        version="0.1.0",
        description="NutriApp profile-service: biometric/health metrics, goal-setting, "
        "and the evolution timeline that powers the user details panel's graphs.",
        lifespan=lifespan,
    )
    app.include_router(profile_router)
    app.include_router(consent_router)
    app.include_router(health_router)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
