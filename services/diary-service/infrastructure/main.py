"""FastAPI application entrypoint. Wires the composition root, routes, the
outbox relay worker, and the diary event projector consumer
(observability-audit SKILL.md, messaging-conventions SKILL.md).
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
from infrastructure.http.routes.daily_summary_routes import router as daily_summary_router
from infrastructure.http.routes.fasting_window_routes import router as fasting_window_router
from infrastructure.http.routes.food_entry_routes import router as food_entry_router
from infrastructure.http.routes.meal_plan_routes import router as meal_plan_router
from infrastructure.http.routes.water_intake_routes import router as water_intake_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container = Container(Settings.from_env())
    await container.startup()
    app.state.container = container
    logger.info("diary_service_started")
    try:
        yield
    finally:
        await container.shutdown()
        logger.info("diary_service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="diary-service",
        version="0.1.0",
        description="NutriApp diary-service: food logging, water intake, fasting windows, "
        "and meal planning -- the primary transactional write path (full event sourcing + CQRS).",
        lifespan=lifespan,
    )
    app.include_router(food_entry_router)
    app.include_router(water_intake_router)
    app.include_router(fasting_window_router)
    app.include_router(meal_plan_router)
    app.include_router(daily_summary_router)
    app.include_router(health_router)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
