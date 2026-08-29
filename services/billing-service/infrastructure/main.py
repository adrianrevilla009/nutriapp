"""FastAPI application entrypoint. Wires the composition root and routes
(messaging-conventions SKILL.md, observability-audit SKILL.md). The
revocation-scan worker runs as a background task started from
Container.startup(), not inline here (mirrors notification-service's
ReminderScanWorker precedent). The outbox relay worker is a separate
process/entrypoint, not started here, same convention as every other
event-driven-CRUD service in this codebase (identity-service/catalog-service).
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
from infrastructure.http.routes.checkout_routes import router as checkout_router
from infrastructure.http.routes.internal_entitlement_routes import (
    router as internal_entitlement_router,
)
from infrastructure.http.routes.stripe_webhook_routes import router as stripe_webhook_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container = Container(Settings.from_env())
    await container.startup()
    app.state.container = container
    logger.info("billing_service_started")
    try:
        yield
    finally:
        await container.shutdown()
        logger.info("billing_service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="billing-service",
        version="0.1.0",
        description="NutriApp billing-service: Pro subscription lifecycle, Stripe "
        "payment processing, and entitlement issuance (ADR-0015).",
        lifespan=lifespan,
    )
    app.include_router(checkout_router)
    app.include_router(stripe_webhook_router)
    app.include_router(internal_entitlement_router)
    app.include_router(health_router)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
