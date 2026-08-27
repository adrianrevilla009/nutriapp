"""FastAPI application entrypoint. Wires the composition root and routes
(messaging-conventions SKILL.md, observability-audit SKILL.md). The
outbox relay worker and the 3 inbound event consumers run as background
tasks/consumers started from Container.startup(), not inline here, same
convention as catalog-service/diary-service.
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
from infrastructure.http.routes.nutrition_total_routes import router as nutrition_total_router
from infrastructure.http.routes.target_routes import router as target_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container = Container(Settings.from_env())
    await container.startup()
    app.state.container = container
    logger.info("nutrition_calculation_service_started")
    try:
        yield
    finally:
        await container.shutdown()
        logger.info("nutrition_calculation_service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="nutrition-calculation-service",
        version="0.1.0",
        description="NutriApp nutrition-calculation-service: macro/micronutrient totals "
        "from diary/catalog data, and Mifflin-St Jeor-based calorie/macro target "
        "computation from profile-service metrics.",
        lifespan=lifespan,
    )
    app.include_router(target_router)
    app.include_router(nutrition_total_router)
    app.include_router(health_router)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
