"""Composition root — the only place concrete adapters are wired to the
ports they satisfy (hexagonal-architecture SKILL.md). Route handlers and
the outbox relay worker depend on this module, never the reverse.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta

import aio_pika
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from infrastructure.cache.redis_rate_limiter import RedisRateLimiter
from infrastructure.messaging.rabbitmq_event_publisher import RabbitMqEventPublisher
from infrastructure.persistence.postgres_audit_repository import PostgresAuditRepository
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository
from infrastructure.persistence.postgres_token_repository import PostgresTokenRepository
from infrastructure.persistence.postgres_user_repository import PostgresUserRepository
from infrastructure.security.argon2_password_hasher import Argon2PasswordHasher
from infrastructure.security.jwt_token_issuer import JwtTokenIssuer

# Matches the NOLOGIN role created by infra/k8s/charts/_lib/templates/
# _db-provision-job.tpl (granted INSERT-only on audit_log by
# migrations/versions/0001_create_identity_tables.py, and granted
# membership TO this service's own DB_ROLE by the provisioning Job, which
# runs with sufficient privilege to do so — the app's own role does not
# have CREATEROLE). Naming convention: "<db-provision roleName>_audit_writer".
AUDIT_WRITER_ROLE = "identity_service_audit_writer"


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    redis_url: str
    rabbitmq_url: str
    jwt_private_key_pem: bytes
    jwt_public_key_pem: bytes
    jwt_key_id: str
    internal_reveal_credential: str
    access_token_ttl: timedelta = timedelta(minutes=15)

    @classmethod
    def from_env(cls) -> Settings:
        private_key_path = os.environ["IDENTITY_JWT_PRIVATE_KEY_PATH"]
        public_key_path = os.environ["IDENTITY_JWT_PUBLIC_KEY_PATH"]
        with open(private_key_path, "rb") as f:
            private_key_pem = f.read()
        with open(public_key_path, "rb") as f:
            public_key_pem = f.read()
        return cls(
            database_url=os.environ["IDENTITY_SERVICE_DATABASE_URL"],
            redis_url=os.environ.get("IDENTITY_SERVICE_REDIS_URL", "redis://localhost:6379/0"),
            rabbitmq_url=os.environ.get(
                "IDENTITY_SERVICE_RABBITMQ_URL", "amqp://guest:guest@localhost/"
            ),
            jwt_private_key_pem=private_key_pem,
            jwt_public_key_pem=public_key_pem,
            jwt_key_id=os.environ.get("IDENTITY_JWT_KEY_ID", "identity-service-key-1"),
            internal_reveal_credential=os.environ["IDENTITY_INTERNAL_REVEAL_CREDENTIAL"],
        )


class Container:
    """Holds long-lived infrastructure clients (DB engine, Redis, RabbitMQ)
    and request-scoped factories for repositories/handlers."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        # Dedicated engine/pool for audit writes: every connection it hands
        # out runs `SET ROLE identity_service_audit_writer` at the Postgres
        # protocol level (asyncpg server_settings, applied at connection
        # start — equivalent to `SET ROLE` immediately after connecting),
        # so the audit repository is *genuinely* restricted to INSERT-only
        # on audit_log for the lifetime of that connection, not just
        # decorated by a migration nobody enforces at runtime
        # (observability-audit SKILL.md, CLAUDE.md §2.8). Deliberately a
        # separate engine/session from `self.engine`, not just a role
        # switch on the shared session: audit writes must never silently
        # downgrade the privilege of whatever else that shared session/
        # transaction is doing.
        self.audit_engine: AsyncEngine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            connect_args={"server_settings": {"role": AUDIT_WRITER_ROLE}},
        )
        self.audit_session_factory = async_sessionmaker(self.audit_engine, expire_on_commit=False)
        # Explicit timeouts (resilience-patterns SKILL.md: "there is no
        # such thing as an acceptable unbounded wait in this codebase").
        # Short values are appropriate here: the rate limiter fails closed
        # (RedisRateLimiter) on any RedisError, including a timeout, so a
        # slow-but-not-dead Redis should fail fast rather than hold up
        # register/login/password-reset-request.
        self.redis = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        self.password_hasher = Argon2PasswordHasher()
        self.token_issuer = JwtTokenIssuer(
            private_key_pem=settings.jwt_private_key_pem,
            public_key_pem=settings.jwt_public_key_pem,
            key_id=settings.jwt_key_id,
            access_token_ttl=settings.access_token_ttl,
        )
        self.rate_limiter = RedisRateLimiter(self.redis)
        self._rabbitmq_connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._event_publisher: RabbitMqEventPublisher | None = None

    async def startup(self) -> None:
        self._rabbitmq_connection = await aio_pika.connect_robust(self.settings.rabbitmq_url)
        self._event_publisher = await RabbitMqEventPublisher.create(self._rabbitmq_connection)

    async def shutdown(self) -> None:
        if self._rabbitmq_connection is not None:
            await self._rabbitmq_connection.close()
        await self.redis.aclose()
        await self.engine.dispose()
        await self.audit_engine.dispose()

    @property
    def event_publisher(self) -> RabbitMqEventPublisher:
        if self._event_publisher is None:
            raise RuntimeError("Container.startup() must be awaited before use.")
        return self._event_publisher

    def new_session(self) -> AsyncSession:
        return self.session_factory()

    def new_audit_session(self) -> AsyncSession:
        return self.audit_session_factory()


def build_repositories(session: AsyncSession, audit_session: AsyncSession):
    """Convenience bundle of the four repository adapters. Users/tokens/
    outbox share one AsyncSession (and therefore one DB transaction) for
    outbox atomicity. `audit_session` is deliberately a separate session
    bound to a separate, privilege-restricted engine (see
    Container.audit_engine) — never the same session as the other three,
    so an audit write can never run with more than INSERT privilege on
    audit_log, and never accidentally shares a transaction whose rollback
    would also erase an already-recorded audit entry."""
    return (
        PostgresUserRepository(session),
        PostgresTokenRepository(session),
        PostgresOutboxRepository(session),
        PostgresAuditRepository(audit_session),
    )
