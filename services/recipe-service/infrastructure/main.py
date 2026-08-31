"""FastAPI application entrypoint. Wires the composition root and routes
(messaging-conventions SKILL.md, observability-audit SKILL.md). The
billing-events consumer and the outbox relay worker both run as
background tasks started from Container.startup(), mirroring
notification-service's/food-recognition-service's precedent.

`search_router` is included BEFORE `recipe_router` deliberately: both
share the `/api/v1/recipes` prefix, and `recipe_router`'s
`GET /{recipe_id}` would otherwise shadow `GET /search` at FastAPI's
routing layer (a literal `/search` path segment must be matched before a
`{recipe_id}: uuid.UUID` path parameter is attempted).
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
from infrastructure.http.routes.recipe_routes import router as recipe_router
from infrastructure.http.routes.search_routes import router as search_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container = Container(Settings.from_env())
    await container.startup()
    app.state.container = container
    logger.info("recipe_service_started")
    try:
        yield
    finally:
        await container.shutdown()
        logger.info("recipe_service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="recipe-service",
        version="0.1.0",
        description="NutriApp recipe-service: user recipe authoring, computed macro/micro "
        "totals, Pro-gated publishing and cross-user recipe search (CLAUDE.md section 2.2).",
        lifespan=lifespan,
    )
    app.include_router(search_router)
    app.include_router(recipe_router)
    app.include_router(health_router)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
