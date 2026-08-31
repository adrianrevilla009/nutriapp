"""Composition root -- the only place concrete adapters are wired to the
ports they satisfy (hexagonal-architecture SKILL.md). Route handlers and
the billing-events consumer all depend on this module, never the reverse.
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

from infrastructure.external.billing_entitlement_client import BillingEntitlementClient
from infrastructure.external.catalog_product_client import CatalogProductClient
from infrastructure.messaging.billing_events_consumer import BillingEventsConsumer
from infrastructure.messaging.outbox_relay_worker import OutboxRelayWorker
from infrastructure.messaging.rabbitmq_event_publisher import RabbitMqEventPublisher
from infrastructure.persistence.postgres_entitlement_cache_repository import (
    PostgresEntitlementCacheRepository,
)
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository
from infrastructure.persistence.postgres_processed_entitlement_events_repository import (
    PostgresProcessedEntitlementEventsRepository,
)
from infrastructure.persistence.postgres_recipe_repository import PostgresRecipeRepository

logger = structlog.get_logger()

DEFAULT_IDENTITY_JWKS_URL = "http://identity-service:8000/.well-known/jwks.json"
DEFAULT_IDENTITY_ISSUER = "identity-service"
DEFAULT_CATALOG_SERVICE_BASE_URL = "http://catalog-service:8000"
DEFAULT_BILLING_SERVICE_BASE_URL = "http://billing-service:8000"


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    rabbitmq_url: str
    identity_jwks_url: str
    identity_issuer: str
    catalog_service_base_url: str
    billing_service_base_url: str
    # Checked against billing-service's internal
    # `GET /internal/v1/billing/entitlements/{user_id}` route's
    # `X-Internal-Service-Credential` header -- billing-service's OWN
    # single shared internal-reveal credential (its route checks against
    # exactly one value, identity-service/catalog-service precedent),
    # read here via a narrow IAM grant on that same Secrets Manager ARN
    # (infra/terraform/environments/dev/recipe-service.tf), not a new
    # per-caller secret. Local-dev default only, the real value is a
    # Terraform-managed secret, never checked in.
    billing_entitlement_credential: str

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            database_url=os.environ["RECIPE_SERVICE_DATABASE_URL"],
            rabbitmq_url=os.environ.get(
                "RECIPE_SERVICE_RABBITMQ_URL", "amqp://guest:guest@localhost/"
            ),
            identity_jwks_url=os.environ.get(
                "RECIPE_SERVICE_IDENTITY_JWKS_URL", DEFAULT_IDENTITY_JWKS_URL
            ),
            identity_issuer=os.environ.get(
                "RECIPE_SERVICE_IDENTITY_ISSUER", DEFAULT_IDENTITY_ISSUER
            ),
            catalog_service_base_url=os.environ.get(
                "RECIPE_SERVICE_CATALOG_SERVICE_BASE_URL", DEFAULT_CATALOG_SERVICE_BASE_URL
            ),
            billing_service_base_url=os.environ.get(
                "RECIPE_SERVICE_BILLING_SERVICE_BASE_URL", DEFAULT_BILLING_SERVICE_BASE_URL
            ),
            billing_entitlement_credential=os.environ.get(
                "RECIPE_SERVICE_BILLING_ENTITLEMENT_CREDENTIAL",
                "local-dev-billing-entitlement-credential-change-me",
            ),
        )


class Container:
    """Holds long-lived infrastructure clients (DB engine, RabbitMQ, the
    two external clients, the JWT verifier) and request-scoped factories
    for repositories/handlers."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

        self.jwt_verifier = JwtVerifier(
            jwks_url=settings.identity_jwks_url, issuer=settings.identity_issuer
        )

        # Own, isolated connection pool + dedicated, independently-named
        # circuit breaker per external dependency (resilience-patterns
        # SKILL.md, implementation plan section 7) -- `catalog_product_lookup`
        # and `billing_entitlement_check` never share breaker state.
        self.catalog_products = CatalogProductClient(base_url=settings.catalog_service_base_url)
        self.entitlement_check = BillingEntitlementClient(
            base_url=settings.billing_service_base_url,
            credential=settings.billing_entitlement_credential,
        )

        self._rabbitmq_connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._event_publisher: RabbitMqEventPublisher | None = None
        self._billing_events_consumer: BillingEventsConsumer | None = None
        self._outbox_relay_worker: OutboxRelayWorker | None = None
        self._background_tasks: list[asyncio.Task[None]] = []

    async def startup(self) -> None:
        self._rabbitmq_connection = await aio_pika.connect_robust(self.settings.rabbitmq_url)
        self._event_publisher = await RabbitMqEventPublisher.create(self._rabbitmq_connection)

        self._billing_events_consumer = BillingEventsConsumer(self.session_factory)
        await self._billing_events_consumer.setup(self._rabbitmq_connection)
        await self._billing_events_consumer.consume()

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
        await self.catalog_products.aclose()
        await self.entitlement_check.aclose()
        await self.engine.dispose()

    def new_session(self) -> AsyncSession:
        return self.session_factory()


def build_repositories(
    session: AsyncSession,
) -> tuple[
    PostgresRecipeRepository,
    PostgresEntitlementCacheRepository,
    PostgresProcessedEntitlementEventsRepository,
    PostgresOutboxRepository,
]:
    """Convenience bundle of the request-scoped repository adapters --
    every repository shares one AsyncSession (and therefore one DB
    transaction) for outbox atomicity, same convention as every other
    service's build_repositories."""
    return (
        PostgresRecipeRepository(session),
        PostgresEntitlementCacheRepository(session),
        PostgresProcessedEntitlementEventsRepository(session),
        PostgresOutboxRepository(session),
    )
