"""FastAPI application entrypoint. Wires the composition root and routes
(messaging-conventions SKILL.md, observability-audit SKILL.md). All three
message consumers run as background tasks started from
Container.startup()."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from infrastructure.composition_root import Container, Settings
from infrastructure.http.health import router as health_router
from infrastructure.http.routes.chat_routes import router as chat_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container = Container(Settings.from_env())
    await container.startup()
    app.state.container = container
    logger.info("nutrition_assistant_service_started")
    try:
        yield
    finally:
        await container.shutdown()
        logger.info("nutrition_assistant_service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="nutrition-assistant-service",
        version="0.1.0",
        description="NutriApp nutrition-assistant-service: RAG-grounded conversational "
        "assistant over the user's own diary/nutrition/analytics history "
        "(CLAUDE.md section 2.2, ADR-0002 event-driven CRUD).",
        lifespan=lifespan,
    )
    app.include_router(chat_router)
    app.include_router(health_router)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
