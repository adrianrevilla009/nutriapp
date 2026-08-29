"""Composition root -- the only place concrete adapters are wired to the
ports they satisfy (hexagonal-architecture SKILL.md). Route handlers and
the revocation-scan worker all depend on this module, never the reverse.
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

from infrastructure.external.stripe_payment_adapter import StripePaymentAdapter
from infrastructure.messaging.rabbitmq_event_publisher import RabbitMqEventPublisher
from infrastructure.persistence.postgres_entitlement_revocation_schedule_repository import (
    PostgresEntitlementRevocationScheduleRepository,
)
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository
from infrastructure.persistence.postgres_processed_webhook_events_repository import (
    PostgresProcessedWebhookEventsRepository,
)
from infrastructure.persistence.postgres_subscription_repository import (
    PostgresSubscriptionRepository,
)
from infrastructure.scheduling.revocation_scan_worker import RevocationScanWorker

logger = structlog.get_logger()

DEFAULT_IDENTITY_JWKS_URL = "http://identity-service:8000/.well-known/jwks.json"
DEFAULT_IDENTITY_ISSUER = "identity-service"
DEFAULT_STRIPE_BASE_URL = "https://api.stripe.com"
DEFAULT_REVOCATION_SCAN_INTERVAL_SECONDS = 60.0


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    rabbitmq_url: str
    identity_jwks_url: str
    identity_issuer: str
    stripe_secret_key: str
    stripe_webhook_signing_secret: str
    stripe_price_id: str
    stripe_base_url: str
    # Checked against the internal `GET /internal/v1/billing/entitlements/{user_id}`
    # route's `X-Internal-Service-Credential` header (implementation plan
    # section 3), same identity-service/catalog-service precedent -- local-
    # dev default only, the real value is a Terraform-managed secret,
    # never checked in.
    internal_entitlement_credential: str
    revocation_scan_interval_seconds: float

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            database_url=os.environ["BILLING_SERVICE_DATABASE_URL"],
            rabbitmq_url=os.environ.get(
                "BILLING_SERVICE_RABBITMQ_URL", "amqp://guest:guest@localhost/"
            ),
            identity_jwks_url=os.environ.get(
                "BILLING_SERVICE_IDENTITY_JWKS_URL", DEFAULT_IDENTITY_JWKS_URL
            ),
            identity_issuer=os.environ.get(
                "BILLING_SERVICE_IDENTITY_ISSUER", DEFAULT_IDENTITY_ISSUER
            ),
            # Real Stripe API key provisioning is a tracked lead-time item
            # (implementation plan section 9, risk 2) -- the placeholder
            # values below are never valid against a real Stripe account,
            # same "DEMO_KEY"-style precedent as catalog-service's USDA FDC
            # default. Deliberately NOT prefixed "sk_test_"/"sk_live_" --
            # that prefix alone (regardless of what follows) trips both
            # gitleaks' stripe-access-token rule and Trivy's image secret
            # scan; this string is never sent to Stripe's real API surface
            # so the exact placeholder format doesn't matter, only that a
            # misconfigured deployment fails loudly rather than silently
            # matching a real-looking key.
            stripe_secret_key=os.environ.get(
                "BILLING_SERVICE_STRIPE_SECRET_KEY", "UNSET_STRIPE_SECRET_KEY"
            ),
            stripe_webhook_signing_secret=os.environ.get(
                "BILLING_SERVICE_STRIPE_WEBHOOK_SIGNING_SECRET", "whsec_placeholder"
            ),
            stripe_price_id=os.environ.get(
                "BILLING_SERVICE_STRIPE_PRICE_ID", "price_pro_monthly_placeholder"
            ),
            stripe_base_url=os.environ.get(
                "BILLING_SERVICE_STRIPE_BASE_URL", DEFAULT_STRIPE_BASE_URL
            ),
            internal_entitlement_credential=os.environ.get(
                "BILLING_INTERNAL_ENTITLEMENT_CREDENTIAL",
                "local-dev-internal-entitlement-credential",
            ),
            revocation_scan_interval_seconds=float(
                os.environ.get(
                    "BILLING_SERVICE_REVOCATION_SCAN_INTERVAL_SECONDS",
                    DEFAULT_REVOCATION_SCAN_INTERVAL_SECONDS,
                )
            ),
        )


class Container:
    """Holds long-lived infrastructure clients (DB engine, RabbitMQ, the
    Stripe adapter, the JWT verifier) and request-scoped factories for
    repositories/handlers."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

        self.jwt_verifier = JwtVerifier(
            jwks_url=settings.identity_jwks_url, issuer=settings.identity_issuer
        )

        self.payment_provider = StripePaymentAdapter(
            secret_key=settings.stripe_secret_key,
            webhook_signing_secret=settings.stripe_webhook_signing_secret,
            price_id=settings.stripe_price_id,
            base_url=settings.stripe_base_url,
        )

        self._rabbitmq_connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._event_publisher: RabbitMqEventPublisher | None = None
        self._revocation_scan_worker: RevocationScanWorker | None = None
        self._background_tasks: list[asyncio.Task[None]] = []

    async def startup(self) -> None:
        self._rabbitmq_connection = await aio_pika.connect_robust(self.settings.rabbitmq_url)
        self._event_publisher = await RabbitMqEventPublisher.create(self._rabbitmq_connection)

        self._revocation_scan_worker = RevocationScanWorker(
            self.session_factory,
            scan_interval_seconds=self.settings.revocation_scan_interval_seconds,
        )
        self._background_tasks.append(
            asyncio.create_task(self._revocation_scan_worker.run_forever())
        )

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
        await self.payment_provider.aclose()
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
    PostgresSubscriptionRepository,
    PostgresProcessedWebhookEventsRepository,
    PostgresEntitlementRevocationScheduleRepository,
    PostgresOutboxRepository,
]:
    """Convenience bundle of the request-scoped repository adapters --
    every repository shares one AsyncSession (and therefore one DB
    transaction) for outbox atomicity, same convention as every other
    service's build_repositories."""
    return (
        PostgresSubscriptionRepository(session),
        PostgresProcessedWebhookEventsRepository(session),
        PostgresEntitlementRevocationScheduleRepository(session),
        PostgresOutboxRepository(session),
    )
