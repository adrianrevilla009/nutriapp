"""Composition root -- the only place concrete adapters are wired to the
ports they satisfy (hexagonal-architecture SKILL.md). Route handlers, the
outbox relay worker, and the diary event projector consumer all depend on
this module, never the reverse.
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

from infrastructure.cache.redis_daily_summary_cache import RedisDailySummaryCache
from infrastructure.messaging.diary_event_projector_consumer import DiaryEventProjectorConsumer
from infrastructure.messaging.outbox_relay_worker import OutboxRelayWorker
from infrastructure.messaging.rabbitmq_event_publisher import RabbitMqEventPublisher

logger = structlog.get_logger()


DEFAULT_IDENTITY_JWKS_URL = "http://identity-service:8000/.well-known/jwks.json"
DEFAULT_IDENTITY_ISSUER = "identity-service"


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    rabbitmq_url: str
    redis_url: str
    identity_jwks_url: str
    identity_issuer: str

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            database_url=os.environ["DIARY_SERVICE_DATABASE_URL"],
            rabbitmq_url=os.environ.get(
                "DIARY_SERVICE_RABBITMQ_URL", "amqp://guest:guest@localhost/"
            ),
            redis_url=os.environ.get("DIARY_SERVICE_REDIS_URL", "redis://localhost:6379/0"),
            identity_jwks_url=os.environ.get(
                "DIARY_SERVICE_IDENTITY_JWKS_URL", DEFAULT_IDENTITY_JWKS_URL
            ),
            identity_issuer=os.environ.get(
                "DIARY_SERVICE_IDENTITY_ISSUER", DEFAULT_IDENTITY_ISSUER
            ),
        )


class Container:
    """Holds long-lived infrastructure clients (DB engine, Redis, RabbitMQ)
    and request-scoped factories for repositories/handlers."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

        self.redis = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        self.daily_summary_cache = RedisDailySummaryCache(self.redis)

        # Verifies identity-service-issued access tokens locally via its
        # published JWKS (ADR-0022) -- no synchronous call back to
        # identity-service on every request, only on a JWKS cache miss/
        # expiry. See infrastructure/http/dependencies.py.
        self.jwt_verifier = JwtVerifier(
            jwks_url=settings.identity_jwks_url, issuer=settings.identity_issuer
        )

        self._rabbitmq_connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._event_publisher: RabbitMqEventPublisher | None = None
        self._projector_consumer: DiaryEventProjectorConsumer | None = None
        self._outbox_relay_worker: OutboxRelayWorker | None = None
        self._background_tasks: list[asyncio.Task[None]] = []

    async def startup(self) -> None:
        self._rabbitmq_connection = await aio_pika.connect_robust(self.settings.rabbitmq_url)
        self._event_publisher = await RabbitMqEventPublisher.create(self._rabbitmq_connection)

        self._outbox_relay_worker = OutboxRelayWorker(self.session_factory, self._event_publisher)
        self._background_tasks.append(asyncio.create_task(self._outbox_relay_worker.run_forever()))

        self._projector_consumer = DiaryEventProjectorConsumer(
            self.session_factory, redis_cache=self.daily_summary_cache
        )
        await self._projector_consumer.setup(self._rabbitmq_connection)
        await self._projector_consumer.consume()

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
        await self.redis.aclose()
        await self.engine.dispose()

    @property
    def event_publisher(self) -> RabbitMqEventPublisher:
        if self._event_publisher is None:
            raise RuntimeError("Container.startup() must be awaited before use.")
        return self._event_publisher

    def new_session(self) -> AsyncSession:
        return self.session_factory()
