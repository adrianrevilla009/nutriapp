"""Composition root -- the only place concrete adapters are wired to the
ports they satisfy (hexagonal-architecture SKILL.md). Route handlers, the
outbox relay worker, and the 3 inbound consumers all depend on this
module, never the reverse. Mirrors services/catalog-service's and
services/diary-service's shape -- this is the first service with 3
simultaneous live inbound event dependencies (implementation plan section
6(b)).
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import aio_pika
import structlog
from redis.asyncio import Redis
from shared_contracts.auth.jwt_verifier import JwtVerifier
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from infrastructure.caching.redis_current_target_cache import RedisCurrentTargetCache
from infrastructure.caching.redis_current_total_cache import RedisCurrentTotalCache
from infrastructure.http.profile_reveal_client import ProfileRevealClient
from infrastructure.messaging.catalog_product_consumer import CatalogProductConsumer
from infrastructure.messaging.diary_food_entry_consumer import DiaryFoodEntryConsumer
from infrastructure.messaging.outbox_relay_worker import OutboxRelayWorker
from infrastructure.messaging.profile_metrics_consumer import ProfileMetricsConsumer
from infrastructure.messaging.rabbitmq_event_publisher import RabbitMqEventPublisher
from infrastructure.persistence.postgres_daily_nutrition_total_repository import (
    PostgresDailyNutritionTotalRepository,
)
from infrastructure.persistence.postgres_nutrient_panel_mirror_repository import (
    PostgresNutrientPanelMirrorRepository,
)
from infrastructure.persistence.postgres_nutrition_target_repository import (
    PostgresNutritionTargetRepository,
)
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository
from infrastructure.persistence.postgres_target_history_repository import (
    PostgresTargetHistoryRepository,
)

logger = structlog.get_logger()

DEFAULT_IDENTITY_JWKS_URL = "http://identity-service:8000/.well-known/jwks.json"
DEFAULT_IDENTITY_ISSUER = "identity-service"
DEFAULT_PROFILE_SERVICE_BASE_URL = "http://profile-service:8001"


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    rabbitmq_url: str
    redis_url: str
    identity_jwks_url: str
    identity_issuer: str
    profile_service_base_url: str
    profile_reveal_credential: str

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            database_url=os.environ["NUTRITION_CALCULATION_SERVICE_DATABASE_URL"],
            rabbitmq_url=os.environ.get(
                "NUTRITION_CALCULATION_SERVICE_RABBITMQ_URL", "amqp://guest:guest@localhost/"
            ),
            redis_url=os.environ.get(
                "NUTRITION_CALCULATION_SERVICE_REDIS_URL", "redis://localhost:6379/2"
            ),
            identity_jwks_url=os.environ.get(
                "NUTRITION_CALCULATION_SERVICE_IDENTITY_JWKS_URL", DEFAULT_IDENTITY_JWKS_URL
            ),
            identity_issuer=os.environ.get(
                "NUTRITION_CALCULATION_SERVICE_IDENTITY_ISSUER", DEFAULT_IDENTITY_ISSUER
            ),
            profile_service_base_url=os.environ.get(
                "NUTRITION_CALCULATION_SERVICE_PROFILE_SERVICE_BASE_URL",
                DEFAULT_PROFILE_SERVICE_BASE_URL,
            ),
            # Per-caller credential, distinct from any other service's secret
            # (implementation plan Addendum 1 security sub-addendum
            # requirement 1) -- sourced from Secrets Manager via External
            # Secrets Operator in a real deployment, never hardcoded.
            profile_reveal_credential=os.environ.get(
                "NUTRITION_CALCULATION_SERVICE_PROFILE_REVEAL_CREDENTIAL", ""
            ),
        )


class Container:
    """Holds long-lived infrastructure clients (DB engine, Redis,
    RabbitMQ, the ProfileRevealClient) and request-scoped factories for
    repositories/handlers."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

        self.redis = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        self.current_target_cache = RedisCurrentTargetCache(self.redis)
        self.current_total_cache = RedisCurrentTotalCache(self.redis)

        self.jwt_verifier = JwtVerifier(
            jwks_url=settings.identity_jwks_url, issuer=settings.identity_issuer
        )

        # Own, isolated connection pool + dedicated circuit breaker
        # (implementation plan Addendum 1 security sub-addendum
        # requirement 7) -- never shared with profile-service's own
        # internal KMS breaker.
        self.profile_reveal_client = ProfileRevealClient(
            base_url=settings.profile_service_base_url,
            credential=settings.profile_reveal_credential,
        )

        self._rabbitmq_connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._event_publisher: RabbitMqEventPublisher | None = None
        self._outbox_relay_worker: OutboxRelayWorker | None = None
        self._diary_consumer: DiaryFoodEntryConsumer | None = None
        self._profile_consumer: ProfileMetricsConsumer | None = None
        self._catalog_consumer: CatalogProductConsumer | None = None
        self._background_tasks: list[asyncio.Task[None]] = []

    async def startup(self) -> None:
        self._rabbitmq_connection = await aio_pika.connect_robust(self.settings.rabbitmq_url)
        self._event_publisher = await RabbitMqEventPublisher.create(self._rabbitmq_connection)

        self._outbox_relay_worker = OutboxRelayWorker(self.session_factory, self._event_publisher)
        self._background_tasks.append(asyncio.create_task(self._outbox_relay_worker.run_forever()))

        self._diary_consumer = DiaryFoodEntryConsumer(
            self.session_factory, redis_cache=self.current_total_cache
        )
        await self._diary_consumer.setup(self._rabbitmq_connection)
        await self._diary_consumer.consume()

        self._profile_consumer = ProfileMetricsConsumer(
            self.session_factory, self.profile_reveal_client, redis_cache=self.current_target_cache
        )
        await self._profile_consumer.setup(self._rabbitmq_connection)
        await self._profile_consumer.consume()

        self._catalog_consumer = CatalogProductConsumer(self.session_factory)
        await self._catalog_consumer.setup(self._rabbitmq_connection)
        await self._catalog_consumer.consume()

    async def shutdown(self) -> None:
        for task in self._background_tasks:
            task.cancel()
        for task in self._background_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("background_task_shutdown_error")
        if self._rabbitmq_connection is not None:
            await self._rabbitmq_connection.close()
        await self.profile_reveal_client.aclose()
        await self.redis.aclose()
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
    PostgresNutritionTargetRepository,
    PostgresTargetHistoryRepository,
    PostgresDailyNutritionTotalRepository,
    PostgresNutrientPanelMirrorRepository,
    PostgresOutboxRepository,
]:
    """Convenience bundle of the request-scoped repository adapters --
    share one AsyncSession (and therefore one DB transaction) for outbox
    atomicity, same convention as catalog-service's build_repositories."""
    return (
        PostgresNutritionTargetRepository(session),
        PostgresTargetHistoryRepository(session),
        PostgresDailyNutritionTotalRepository(session),
        PostgresNutrientPanelMirrorRepository(session),
        PostgresOutboxRepository(session),
    )
