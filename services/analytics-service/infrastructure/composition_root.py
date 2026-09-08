"""Composition root -- the only place concrete adapters are wired to the
ports they satisfy (hexagonal-architecture SKILL.md). Route handlers and
all four consumers depend on this module, never the reverse."""

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
from infrastructure.messaging.billing_events_consumer import BillingEventsConsumer
from infrastructure.messaging.diary_events_consumer import DiaryEventsConsumer
from infrastructure.messaging.nutrition_calculation_events_consumer import (
    NutritionCalculationEventsConsumer,
)
from infrastructure.messaging.outbox_relay_worker import OutboxRelayWorker
from infrastructure.messaging.profile_events_consumer import ProfileEventsConsumer
from infrastructure.messaging.rabbitmq_event_publisher import RabbitMqEventPublisher
from infrastructure.messaging.resilient_topic_consumer import ResilientTopicConsumer
from infrastructure.persistence.postgres_anomaly_alerts_repository import (
    PostgresAnomalyAlertsRepository,
)
from infrastructure.persistence.postgres_daily_log_summary_repository import (
    PostgresDailyLogSummaryRepository,
)
from infrastructure.persistence.postgres_entitlement_cache_repository import (
    PostgresEntitlementCacheRepository,
)
from infrastructure.persistence.postgres_export_audit_repository import (
    PostgresExportAuditRepository,
)
from infrastructure.persistence.postgres_micronutrient_window_repository import (
    PostgresMicronutrientWindowRepository,
)
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository

logger = structlog.get_logger()

DEFAULT_IDENTITY_JWKS_URL = "http://identity-service:8000/.well-known/jwks.json"
DEFAULT_IDENTITY_ISSUER = "identity-service"
DEFAULT_BILLING_SERVICE_BASE_URL = "http://billing-service:8000"

# Append-only export-audit privilege separation (CLAUDE.md section 2.8,
# docs/observability-and-audit.md section 4.3, .claude/skills/
# observability-audit/SKILL.md) -- exact same mechanism as
# identity-service's `AUDIT_WRITER_ROLE`/`Container.audit_engine` and
# profile-service's own copy of it. The role itself is created by
# infra/k8s/charts/_lib/templates/_db-provision-job.tpl (running as the
# RDS master user, which has CREATEROLE) as "<DB_ROLE>_audit_writer" ==
# "analytics_service_audit_writer" for this service -- this module never
# creates the role, only connects as it.
AUDIT_WRITER_ROLE = "analytics_service_audit_writer"


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    rabbitmq_url: str
    identity_jwks_url: str
    identity_issuer: str
    billing_service_base_url: str
    # Checked against billing-service's internal
    # `GET /internal/v1/billing/entitlements/{user_id}` route's
    # `X-Internal-Service-Credential` header -- billing-service's OWN
    # single shared internal-reveal credential (recipe-service's/
    # social-service's precedent), read here via a narrow IAM grant on
    # that same Secrets Manager ARN (infra/terraform/environments/dev/
    # analytics-service.tf). Local-dev default only.
    billing_entitlement_credential: str

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            database_url=os.environ["ANALYTICS_SERVICE_DATABASE_URL"],
            rabbitmq_url=os.environ.get(
                "ANALYTICS_SERVICE_RABBITMQ_URL", "amqp://guest:guest@localhost/"
            ),
            identity_jwks_url=os.environ.get(
                "ANALYTICS_SERVICE_IDENTITY_JWKS_URL", DEFAULT_IDENTITY_JWKS_URL
            ),
            identity_issuer=os.environ.get(
                "ANALYTICS_SERVICE_IDENTITY_ISSUER", DEFAULT_IDENTITY_ISSUER
            ),
            billing_service_base_url=os.environ.get(
                "ANALYTICS_SERVICE_BILLING_SERVICE_BASE_URL", DEFAULT_BILLING_SERVICE_BASE_URL
            ),
            billing_entitlement_credential=os.environ.get(
                "ANALYTICS_SERVICE_BILLING_ENTITLEMENT_CREDENTIAL",
                "local-dev-billing-entitlement-credential-change-me",
            ),
        )


class Container:
    """Holds long-lived infrastructure clients (DB engine, RabbitMQ, the
    entitlement client, the JWT verifier) and request-scoped factories for
    repositories/handlers. Starts all four topic consumers plus the outbox
    relay worker as background tasks (recipe-service's/social-service's
    precedent)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

        # Dedicated engine/pool for export-audit writes: every connection it
        # hands out runs `SET ROLE analytics_service_audit_writer` at the
        # Postgres protocol level (`connect_args["server_settings"]`, applied
        # once per physical connection, not a `SET ROLE` on the shared
        # session), so `PostgresExportAuditRepository` is *genuinely*
        # restricted to INSERT/SELECT on `analytics_audit.export_audit_log`
        # for the lifetime of that connection, not just a role switch on the
        # shared session -- an audit write must never silently gain
        # UPDATE/DELETE just because it shares a connection with a read
        # repository (identity-service's/profile-service's identical
        # precedent; observability-audit SKILL.md, CLAUDE.md section 2.8).
        self.audit_engine: AsyncEngine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            connect_args={"server_settings": {"role": AUDIT_WRITER_ROLE}},
        )
        self.audit_session_factory = async_sessionmaker(self.audit_engine, expire_on_commit=False)

        self.jwt_verifier = JwtVerifier(
            jwks_url=settings.identity_jwks_url, issuer=settings.identity_issuer
        )

        self.entitlement_check = BillingEntitlementClient(
            base_url=settings.billing_service_base_url,
            credential=settings.billing_entitlement_credential,
        )

        self._rabbitmq_connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._event_publisher: RabbitMqEventPublisher | None = None
        self._consumers: list[ResilientTopicConsumer] = []
        self._outbox_relay_worker: OutboxRelayWorker | None = None
        self._background_tasks: list[asyncio.Task[None]] = []

    async def _start_consumer(self, consumer: ResilientTopicConsumer) -> None:
        assert self._rabbitmq_connection is not None
        await consumer.setup(self._rabbitmq_connection)
        await consumer.consume()
        self._consumers.append(consumer)

    async def startup(self) -> None:
        self._rabbitmq_connection = await aio_pika.connect_robust(self.settings.rabbitmq_url)
        self._event_publisher = await RabbitMqEventPublisher.create(self._rabbitmq_connection)

        await self._start_consumer(DiaryEventsConsumer(self.session_factory))
        await self._start_consumer(ProfileEventsConsumer(self.session_factory))
        await self._start_consumer(NutritionCalculationEventsConsumer(self.session_factory))
        await self._start_consumer(BillingEventsConsumer(self.session_factory))

        self._outbox_relay_worker = OutboxRelayWorker(self.session_factory, self._event_publisher)
        self._background_tasks.append(asyncio.create_task(self._outbox_relay_worker.run_forever()))

    async def _cancel_background_tasks(self) -> None:
        if not self._background_tasks:
            return

        for task in self._background_tasks:
            task.cancel()

        outcomes = await asyncio.gather(*self._background_tasks, return_exceptions=True)
        for outcome in outcomes:
            is_unexpected_failure = isinstance(outcome, BaseException) and not isinstance(
                outcome, asyncio.CancelledError
            )
            if is_unexpected_failure:
                logger.exception("background_task_shutdown_error", exc_info=outcome)

    async def shutdown(self) -> None:
        await self._cancel_background_tasks()
        if self._rabbitmq_connection is not None:
            await self._rabbitmq_connection.close()
        await self.entitlement_check.aclose()
        await self.engine.dispose()
        await self.audit_engine.dispose()

    def new_session(self) -> AsyncSession:
        return self.session_factory()

    def new_audit_session(self) -> AsyncSession:
        """Separate session bound to `Container.audit_engine` (never the
        shared `session_factory`) -- see that attribute's docstring."""
        return self.audit_session_factory()


def build_repositories(
    session: AsyncSession,
    audit_session: AsyncSession | None = None,
) -> tuple[
    PostgresDailyLogSummaryRepository,
    PostgresMicronutrientWindowRepository,
    PostgresAnomalyAlertsRepository,
    PostgresEntitlementCacheRepository,
    PostgresExportAuditRepository,
    PostgresOutboxRepository,
]:
    """Convenience bundle of the request-scoped repository adapters used by
    the HTTP routes -- every repository except the export-audit one shares
    one AsyncSession (and therefore one DB transaction), same convention as
    every other service's `build_repositories`. `PostgresExportAuditRepository`
    is deliberately given its own session (`audit_session`, expected to be
    `Container.new_audit_session()`) so an audit write can never run with
    more than INSERT/SELECT privilege on `export_audit_log`, and never
    accidentally shares a transaction whose rollback would also erase an
    already-recorded audit entry -- callers that don't care about the
    export-audit repository (e.g. `trend_routes.py`, which never touches
    Pro-gated exports) may omit `audit_session` and get the shared session
    instead, since the returned repository is simply discarded there. The
    four `Processed*EventsRepositoryPort` ledgers are NOT part of this
    bundle -- only the four message consumers use them, which construct
    their own repositories directly (mirrors recipe-service's/
    social-service's consumer precedent)."""
    return (
        PostgresDailyLogSummaryRepository(session),
        PostgresMicronutrientWindowRepository(session),
        PostgresAnomalyAlertsRepository(session),
        PostgresEntitlementCacheRepository(session),
        PostgresExportAuditRepository(audit_session or session),
        PostgresOutboxRepository(session),
    )
