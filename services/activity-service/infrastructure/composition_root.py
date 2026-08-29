"""Composition root -- the only place concrete adapters are wired to the
ports they satisfy (hexagonal-architecture SKILL.md). Route handlers and
the outbox relay worker depend on this module, never the reverse. Mirrors
services/catalog-service/infrastructure/composition_root.py's shape --
event-driven CRUD, conventional persistence, no caching layer needed
(implementation plan section 7).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import aio_pika
from shared_contracts.auth.jwt_verifier import JwtVerifier
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from infrastructure.messaging.rabbitmq_event_publisher import RabbitMqEventPublisher
from infrastructure.persistence.postgres_exercise_repository import PostgresExerciseRepository
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    rabbitmq_url: str
    identity_jwks_url: str

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            database_url=os.environ["ACTIVITY_SERVICE_DATABASE_URL"],
            rabbitmq_url=os.environ.get(
                "ACTIVITY_SERVICE_RABBITMQ_URL", "amqp://guest:guest@localhost/"
            ),
            identity_jwks_url=os.environ.get(
                "ACTIVITY_SERVICE_IDENTITY_JWKS_URL",
                "http://localhost:8000/.well-known/jwks.json",
            ),
        )


class Container:
    """Holds long-lived infrastructure clients (DB engine, RabbitMQ) and
    request-scoped factories for repositories/handlers."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        self.jwt_verifier = JwtVerifier(jwks_url=settings.identity_jwks_url)
        self._rabbitmq_connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._event_publisher: RabbitMqEventPublisher | None = None

    async def startup(self) -> None:
        self._rabbitmq_connection = await aio_pika.connect_robust(self.settings.rabbitmq_url)
        self._event_publisher = await RabbitMqEventPublisher.create(self._rabbitmq_connection)

    async def shutdown(self) -> None:
        if self._rabbitmq_connection is not None:
            await self._rabbitmq_connection.close()
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
) -> tuple[PostgresExerciseRepository, PostgresOutboxRepository]:
    """Convenience bundle of the request-scoped repository adapters --
    exercise/outbox share one AsyncSession (and therefore one DB
    transaction) for outbox atomicity, same convention as every other
    service's build_repositories."""
    return (
        PostgresExerciseRepository(session),
        PostgresOutboxRepository(session),
    )
