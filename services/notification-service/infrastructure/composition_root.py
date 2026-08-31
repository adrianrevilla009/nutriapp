"""Composition root -- the only place concrete adapters are wired to the
ports they satisfy (hexagonal-architecture SKILL.md). Route handlers,
message consumers, and the reminder-scan worker all depend on this
module, never the reverse.
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

from infrastructure.external.identity_token_reveal_client import IdentityTokenRevealClient
from infrastructure.external.ses_email_adapter import SesEmailAdapter
from infrastructure.external.sns_push_adapter import SnsPushAdapter
from infrastructure.messaging.diary_events_consumer import DiaryEventsConsumer
from infrastructure.messaging.identity_events_consumer import IdentityEventsConsumer
from infrastructure.messaging.social_events_consumer import SocialEventsConsumer
from infrastructure.persistence.postgres_preferences_repository import (
    PostgresPreferencesRepository,
)
from infrastructure.scheduling.pending_push_dispatch_scan_worker import (
    PendingPushDispatchScanWorker,
)
from infrastructure.scheduling.reminder_scan_worker import ReminderScanWorker
from infrastructure.templating.jinja_template_renderer import JinjaTemplateRenderer

logger = structlog.get_logger()

DEFAULT_IDENTITY_JWKS_URL = "http://identity-service:8000/.well-known/jwks.json"
DEFAULT_IDENTITY_ISSUER = "identity-service"
DEFAULT_IDENTITY_SERVICE_BASE_URL = "http://identity-service:8000"
DEFAULT_SES_BASE_URL = "http://localhost:9001"
DEFAULT_SNS_BASE_URL = "http://localhost:9002"
DEFAULT_SES_FROM_ADDRESS = "no-reply@nutriapp.example"
DEFAULT_REMINDER_SCAN_INTERVAL_SECONDS = 60.0
DEFAULT_PENDING_PUSH_DISPATCH_SCAN_INTERVAL_SECONDS = 60.0


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    rabbitmq_url: str
    identity_jwks_url: str
    identity_issuer: str
    identity_service_base_url: str
    # Read access to identity-service's single, shared internal-reveal
    # credential (module.secrets.internal_reveal_credential_secret_arns
    # ["identity-service"]) -- NOT the newer per-caller
    # cross_service_reveal_credential mechanism catalog-service/
    # food-recognition-service use, because identity-service's reveal
    # endpoint predates that mechanism and deliberately keeps its
    # existing single-shared-credential design (docs/api-catalog.md).
    identity_reveal_credential: str
    ses_base_url: str
    ses_from_address: str
    sns_base_url: str
    reminder_scan_interval_seconds: float
    pending_push_dispatch_scan_interval_seconds: float

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            database_url=os.environ["NOTIFICATION_SERVICE_DATABASE_URL"],
            rabbitmq_url=os.environ.get(
                "NOTIFICATION_SERVICE_RABBITMQ_URL", "amqp://guest:guest@localhost/"
            ),
            identity_jwks_url=os.environ.get(
                "NOTIFICATION_SERVICE_IDENTITY_JWKS_URL", DEFAULT_IDENTITY_JWKS_URL
            ),
            identity_issuer=os.environ.get(
                "NOTIFICATION_SERVICE_IDENTITY_ISSUER", DEFAULT_IDENTITY_ISSUER
            ),
            identity_service_base_url=os.environ.get(
                "NOTIFICATION_SERVICE_IDENTITY_SERVICE_BASE_URL", DEFAULT_IDENTITY_SERVICE_BASE_URL
            ),
            identity_reveal_credential=os.environ.get(
                "NOTIFICATION_SERVICE_IDENTITY_REVEAL_CREDENTIAL", ""
            ),
            ses_base_url=os.environ.get("NOTIFICATION_SERVICE_SES_BASE_URL", DEFAULT_SES_BASE_URL),
            ses_from_address=os.environ.get(
                "NOTIFICATION_SERVICE_SES_FROM_ADDRESS", DEFAULT_SES_FROM_ADDRESS
            ),
            sns_base_url=os.environ.get("NOTIFICATION_SERVICE_SNS_BASE_URL", DEFAULT_SNS_BASE_URL),
            reminder_scan_interval_seconds=float(
                os.environ.get(
                    "NOTIFICATION_SERVICE_REMINDER_SCAN_INTERVAL_SECONDS",
                    DEFAULT_REMINDER_SCAN_INTERVAL_SECONDS,
                )
            ),
            pending_push_dispatch_scan_interval_seconds=float(
                os.environ.get(
                    "NOTIFICATION_SERVICE_PENDING_PUSH_DISPATCH_SCAN_INTERVAL_SECONDS",
                    DEFAULT_PENDING_PUSH_DISPATCH_SCAN_INTERVAL_SECONDS,
                )
            ),
        )


class Container:
    """Holds long-lived infrastructure clients (DB engine, RabbitMQ, the
    three external adapters, the template renderer) and request-scoped
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
        # shared between any two of these three.
        self.token_reveal_client = IdentityTokenRevealClient(
            base_url=settings.identity_service_base_url,
            credential=settings.identity_reveal_credential,
        )
        self.email_provider = SesEmailAdapter(
            base_url=settings.ses_base_url, from_address=settings.ses_from_address
        )
        self.push_provider = SnsPushAdapter(base_url=settings.sns_base_url)
        self.template_renderer = JinjaTemplateRenderer()

        self._rabbitmq_connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._identity_events_consumer: IdentityEventsConsumer | None = None
        self._diary_events_consumer: DiaryEventsConsumer | None = None
        self._social_events_consumer: SocialEventsConsumer | None = None
        self._reminder_scan_worker: ReminderScanWorker | None = None
        self._pending_push_dispatch_scan_worker: PendingPushDispatchScanWorker | None = None
        self._background_tasks: list[asyncio.Task[None]] = []

    async def startup(self) -> None:
        self._rabbitmq_connection = await aio_pika.connect_robust(self.settings.rabbitmq_url)

        self._identity_events_consumer = IdentityEventsConsumer(
            self.session_factory,
            self.token_reveal_client,
            self.email_provider,
            self.template_renderer,
        )
        await self._identity_events_consumer.setup(self._rabbitmq_connection)
        await self._identity_events_consumer.consume()

        self._diary_events_consumer = DiaryEventsConsumer(self.session_factory)
        await self._diary_events_consumer.setup(self._rabbitmq_connection)
        await self._diary_events_consumer.consume()

        # social-service PR A (/plans/social-service/implementation-plan.md
        # section 6): a real, live consumer of UserFollowed -- wired here
        # so the event is never published (once social-service exists)
        # with nothing listening.
        self._social_events_consumer = SocialEventsConsumer(
            self.session_factory, self.push_provider, self.template_renderer
        )
        await self._social_events_consumer.setup(self._rabbitmq_connection)
        await self._social_events_consumer.consume()

        self._reminder_scan_worker = ReminderScanWorker(
            self.session_factory,
            self.push_provider,
            self.template_renderer,
            scan_interval_seconds=self.settings.reminder_scan_interval_seconds,
        )
        self._background_tasks.append(asyncio.create_task(self._reminder_scan_worker.run_forever()))

        # UserFollowed PR B (quiet-hours fix): retries any new_follower push
        # deferred past quiet hours by SendNewFollowerPushHandler -- wired
        # here so a persisted pending_push_dispatch row is never stuck with
        # nothing scanning it.
        self._pending_push_dispatch_scan_worker = PendingPushDispatchScanWorker(
            self.session_factory,
            self.push_provider,
            self.template_renderer,
            scan_interval_seconds=self.settings.pending_push_dispatch_scan_interval_seconds,
        )
        self._background_tasks.append(
            asyncio.create_task(self._pending_push_dispatch_scan_worker.run_forever())
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
        await self.token_reveal_client.aclose()
        await self.email_provider.aclose()
        await self.push_provider.aclose()
        await self.engine.dispose()

    def new_session(self) -> AsyncSession:
        return self.session_factory()


def build_preferences_repository(session: AsyncSession) -> PostgresPreferencesRepository:
    return PostgresPreferencesRepository(session)
