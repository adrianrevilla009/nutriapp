"""FastAPI application entrypoint(s). Wires the composition root, routes,
the outbox relay worker, and the UserRegistered consumer
(observability-audit SKILL.md, messaging-conventions SKILL.md).

Two ASGI apps, two ports (implementation plan Addendum 2, requirement 3):
  - `create_app()` -- the PUBLIC app, routed through Kong
    (`/api/v1/profile/*`, `/health/*`, `/metrics`). Listens on
    `Settings.public_port` (default 8000).
  - `create_internal_app()` -- the INTERNAL-ONLY app
    (`/internal/v1/profile/{user_id}/reveal-metrics`), never routed through
    Kong. Listens on `Settings.internal_port` (default 8001), a distinct
    port so the NetworkPolicy (infra/k8s/charts/profile-service/values.yaml)
    can restrict it to nutrition-calculation-service's pod selector only,
    excluding Kong entirely -- a genuinely separate listening socket, not
    just a second `from` entry on the same port identity-service's
    `.../reveal` precedent uses (that precedent was reviewed and found
    insufficient for this endpoint's disclosure of Article 9 health data --
    see the query handler's module docstring). Each app deliberately
    excludes the other's routes: even a NetworkPolicy misconfiguration
    would not expose the public API on the internal port or vice versa.

Both apps share ONE `Container` (one DB pool, one KMS client, one Redis
client, one RabbitMQ connection) when run together via `run()` -- a
bulkhead only at the resource-pool level the two ASGI servers use most
differently (Redis for the internal app, RabbitMQ for the public app),
not full process isolation. `python -m infrastructure.main` (this
module's `__main__` entrypoint, wired as the Dockerfile's CMD) is the
production entrypoint; `app`/`internal_app` module-level attributes remain
available for any tool that still expects `uvicorn infrastructure.main:app`
(each such standalone invocation constructs and owns its own Container).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from infrastructure.composition_root import Container, Settings
from infrastructure.http.health import router as health_router
from infrastructure.http.routes.consent_routes import router as consent_router
from infrastructure.http.routes.internal_reveal_metrics_routes import (
    router as internal_reveal_metrics_router,
)
from infrastructure.http.routes.profile_routes import router as profile_router

logger = structlog.get_logger()


def create_app(container: Container | None = None) -> FastAPI:
    """The PUBLIC app -- routed through Kong. If `container` is given, this
    app does not own its start/stop lifecycle (the caller does, see
    `run()`); otherwise it constructs and owns its own (standalone
    invocation, e.g. `uvicorn infrastructure.main:app`)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owns_container = container is None
        active_container = container if container is not None else Container(Settings.from_env())
        if owns_container:
            await active_container.startup()
        app.state.container = active_container
        logger.info("profile_service_public_started")
        try:
            yield
        finally:
            if owns_container:
                await active_container.shutdown()
            logger.info("profile_service_public_stopped")

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


def create_internal_app(container: Container | None = None) -> FastAPI:
    """The INTERNAL-ONLY app -- never routed through Kong (implementation
    plan Addendum 2). Deliberately excludes every public route -- only the
    reveal-metrics route plus health checks. No public OpenAPI docs
    surface either (`docs_url`/`redoc_url`/`openapi_url` disabled) --
    additional defense in depth beyond the NetworkPolicy boundary."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owns_container = container is None
        active_container = container if container is not None else Container(Settings.from_env())
        if owns_container:
            # Standalone invocation only -- the internal app never needs
            # RabbitMQ/the outbox relay/the UserRegistered consumer, so it
            # deliberately does NOT call `active_container.startup()`.
            logger.info("profile_service_internal_standalone_container_created")
        app.state.container = active_container
        logger.info("profile_service_internal_started")
        try:
            yield
        finally:
            if owns_container:
                await active_container.shutdown()
            logger.info("profile_service_internal_stopped")

    app = FastAPI(
        title="profile-service-internal",
        version="0.1.0",
        description="NutriApp profile-service internal-only surface: reveal-metrics "
        "for nutrition-calculation-service. Never routed through Kong.",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.include_router(internal_reveal_metrics_router)
    app.include_router(health_router)
    return app


async def run() -> None:
    """Production entrypoint (Dockerfile CMD: `python -m infrastructure.main`).
    Runs the public and internal apps concurrently, on two distinct ports,
    in this same process, sharing one Container."""
    settings = Settings.from_env()
    container = Container(settings)
    await container.startup()

    public_app = create_app(container)
    internal_app = create_internal_app(container)

    public_server = uvicorn.Server(
        uvicorn.Config(public_app, host="0.0.0.0", port=settings.public_port)
    )
    internal_server = uvicorn.Server(
        uvicorn.Config(internal_app, host="0.0.0.0", port=settings.internal_port)
    )
    try:
        await asyncio.gather(public_server.serve(), internal_server.serve())
    finally:
        await container.shutdown()


app = create_app()
internal_app = create_internal_app()


if __name__ == "__main__":
    asyncio.run(run())
