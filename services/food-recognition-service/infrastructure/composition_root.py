"""Composition root -- the only place concrete adapters are wired to the
ports they satisfy (hexagonal-architecture SKILL.md). Route handlers and
the outbox relay worker all depend on this module, never the reverse.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import aio_pika
import structlog
from shared_contracts.auth.jwt_verifier import JwtVerifier
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from infrastructure.external.catalog_lookup_client import CatalogLookupClient
from infrastructure.external.claude_vision_adapter import DEFAULT_MODEL, ClaudeVisionAdapter
from infrastructure.messaging.outbox_relay_worker import OutboxRelayWorker
from infrastructure.messaging.rabbitmq_event_publisher import RabbitMqEventPublisher
from infrastructure.persistence.postgres_barcode_lookup_repository import (
    PostgresBarcodeLookupRepository,
)
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository
from infrastructure.persistence.postgres_photo_analysis_repository import (
    PostgresPhotoAnalysisRepository,
)
from infrastructure.recognition.pyzbar_barcode_decoder import PyzbarBarcodeDecoder

logger = structlog.get_logger()

DEFAULT_IDENTITY_JWKS_URL = "http://identity-service:8000/.well-known/jwks.json"
DEFAULT_IDENTITY_ISSUER = "identity-service"
DEFAULT_CATALOG_SERVICE_BASE_URL = "http://catalog-service:8000"
DEFAULT_CONFIDENCE_THRESHOLD = 0.6


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    rabbitmq_url: str
    identity_jwks_url: str
    identity_issuer: str
    anthropic_api_key: str
    vision_model: str
    catalog_service_base_url: str
    catalog_lookup_credential: str
    # Tunable via config, never a hardcoded magic number (media-recognition-
    # conventions SKILL.md / implementation plan section 1, acceptance
    # criterion 2). Deliberately NOT namespaced with `_SERVICE_` like the
    # infra-plumbing settings below -- this is a product-facing feature
    # knob, named exactly as specified in the implementation plan.
    confidence_threshold: float
    # Feature flag (implementation plan section 8.3, acceptance criterion
    # 9): a kill switch capable of disabling photo analysis without a
    # deploy if cost or accuracy runs away. Barcode lookup is free/local
    # and is never gated. A full Unleash SDK integration
    # (`.claude/skills/feature-flags/SKILL.md`) is deferred until
    # `packages/feature-flags-client` exists (no service in this repo
    # wires Unleash yet) -- this env-var-based flag has the same
    # boolean-gate shape and is a drop-in swap later, documented in
    # README.md.
    photo_analysis_enabled: bool

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            database_url=os.environ["FOOD_RECOGNITION_SERVICE_DATABASE_URL"],
            rabbitmq_url=os.environ.get(
                "FOOD_RECOGNITION_SERVICE_RABBITMQ_URL", "amqp://guest:guest@localhost/"
            ),
            identity_jwks_url=os.environ.get(
                "FOOD_RECOGNITION_SERVICE_IDENTITY_JWKS_URL", DEFAULT_IDENTITY_JWKS_URL
            ),
            identity_issuer=os.environ.get(
                "FOOD_RECOGNITION_SERVICE_IDENTITY_ISSUER", DEFAULT_IDENTITY_ISSUER
            ),
            # Metered external-API secret (implementation plan section 6(b))
            # -- Terraform-managed, IRSA-scoped to this service only, never
            # hardcoded.
            anthropic_api_key=os.environ.get("FOOD_RECOGNITION_SERVICE_ANTHROPIC_API_KEY", ""),
            vision_model=os.environ.get("FOOD_RECOGNITION_SERVICE_VISION_MODEL", DEFAULT_MODEL),
            catalog_service_base_url=os.environ.get(
                "FOOD_RECOGNITION_SERVICE_CATALOG_SERVICE_BASE_URL",
                DEFAULT_CATALOG_SERVICE_BASE_URL,
            ),
            # Per-caller credential (implementation plan section 6(c)),
            # distinct from any other service's secret -- sourced from
            # Secrets Manager via External Secrets Operator in a real
            # deployment, never hardcoded.
            catalog_lookup_credential=os.environ.get(
                "FOOD_RECOGNITION_SERVICE_CATALOG_LOOKUP_CREDENTIAL", ""
            ),
            confidence_threshold=float(
                os.environ.get(
                    "FOOD_RECOGNITION_CONFIDENCE_THRESHOLD", DEFAULT_CONFIDENCE_THRESHOLD
                )
            ),
            photo_analysis_enabled=_bool_env("FOOD_RECOGNITION_PHOTO_ANALYSIS_ENABLED", True),
        )


class Container:
    """Holds long-lived infrastructure clients (DB engine, RabbitMQ, the
    ClaudeVisionAdapter, the CatalogLookupClient) and request-scoped
    factories for repositories/handlers."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

        self.jwt_verifier = JwtVerifier(
            jwks_url=settings.identity_jwks_url, issuer=settings.identity_issuer
        )

        # Own, isolated connection pool + dedicated circuit breaker per
        # external dependency (resilience-patterns SKILL.md) -- never
        # shared between the two.
        self.vision_adapter = ClaudeVisionAdapter(
            api_key=settings.anthropic_api_key, model=settings.vision_model
        )
        self.catalog_lookup_client = CatalogLookupClient(
            base_url=settings.catalog_service_base_url,
            credential=settings.catalog_lookup_credential,
        )
        self.barcode_decoder = PyzbarBarcodeDecoder()

        self._rabbitmq_connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._event_publisher: RabbitMqEventPublisher | None = None
        self._outbox_relay_worker: OutboxRelayWorker | None = None
        self._background_tasks: list[asyncio.Task[None]] = []

    async def startup(self) -> None:
        self._rabbitmq_connection = await aio_pika.connect_robust(self.settings.rabbitmq_url)
        self._event_publisher = await RabbitMqEventPublisher.create(self._rabbitmq_connection)

        self._outbox_relay_worker = OutboxRelayWorker(self.session_factory, self._event_publisher)
        self._background_tasks.append(asyncio.create_task(self._outbox_relay_worker.run_forever()))

    async def shutdown(self) -> None:
        for task in self._background_tasks:
            task.cancel()
        if self._background_tasks:
            results = await asyncio.gather(*self._background_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, BaseException) and not isinstance(
                    result, asyncio.CancelledError
                ):
                    logger.exception("background_task_shutdown_error", exc_info=result)
        if self._rabbitmq_connection is not None:
            await self._rabbitmq_connection.close()
        await self.vision_adapter.aclose()
        await self.catalog_lookup_client.aclose()
        await self.engine.dispose()

    @property
    def event_publisher(self) -> RabbitMqEventPublisher:
        if self._event_publisher is None:
            raise RuntimeError("Container.startup() must be awaited before use.")
        return self._event_publisher

    def new_session(self) -> AsyncSession:
        return self.session_factory()


def build_repositories(
    session: AsyncSession,
) -> tuple[
    PostgresPhotoAnalysisRepository,
    PostgresBarcodeLookupRepository,
    PostgresOutboxRepository,
]:
    """Convenience bundle of the request-scoped repository adapters --
    share one AsyncSession (and therefore one DB transaction) for outbox
    atomicity, same convention as every other service."""
    return (
        PostgresPhotoAnalysisRepository(session),
        PostgresBarcodeLookupRepository(session),
        PostgresOutboxRepository(session),
    )
