"""Composition root -- the only place concrete adapters are wired to the
ports they satisfy (hexagonal-architecture SKILL.md). Route handlers, the
outbox relay worker, and the UserRegistered consumer all depend on this
module, never the reverse.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field

import aio_pika
import boto3
import structlog
from botocore.config import Config as BotoConfig
from redis.asyncio import Redis
from shared_contracts.auth.jwt_verifier import JwtVerifier
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from application.queries.get_biometric_snapshot_for_calculation import (
    DEFAULT_REVEAL_RATE_LIMIT,
    DEFAULT_REVEAL_RATE_LIMIT_WINDOW_SECONDS,
)
from infrastructure.cache.redis_rate_limiter import RedisRateLimiter
from infrastructure.messaging.outbox_relay_worker import OutboxRelayWorker
from infrastructure.messaging.rabbitmq_event_publisher import RabbitMqEventPublisher
from infrastructure.messaging.user_registered_consumer import UserRegisteredConsumer
from infrastructure.security.kms_envelope_data_encryption import (
    DEFAULT_CALL_TIMEOUT_SECONDS,
    KmsEnvelopeDataEncryption,
)

logger = structlog.get_logger()


DEFAULT_IDENTITY_JWKS_URL = "http://identity-service:8000/.well-known/jwks.json"
DEFAULT_IDENTITY_ISSUER = "identity-service"
DEFAULT_PUBLIC_PORT = 8000
DEFAULT_INTERNAL_PORT = 8001

# Matches the NOLOGIN role created by infra/k8s/charts/_lib/templates/
# _db-provision-job.tpl ("<dbProvision.roleName>_audit_writer" ==
# "profile_service_audit_writer" for this service, granted INSERT-only on
# audit_records by migrations/versions/0003_create_audit_records_table.py)
# -- exact same mechanism as identity-service's AUDIT_WRITER_ROLE.
AUDIT_WRITER_ROLE = "profile_service_audit_writer"

# Caller name for nutrition-calculation-service's credential (implementation
# plan Addendum 2) -- used as the audit trail's `actor_id` whenever this
# credential is the one presented. A distinct, per-caller credential (never
# identity-service's shared secret, never a generic "any internal caller"
# credential) -- see PROFILE_SERVICE_REVEAL_CREDENTIAL_NUTRITION_CALC below
# and infra/terraform/modules/secrets/main.tf's
# `cross_service_reveal_credential` resources.
NUTRITION_CALCULATION_SERVICE_ACTOR = "nutrition-calculation-service"


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    rabbitmq_url: str
    aws_region: str
    kms_key_id: str
    identity_jwks_url: str
    identity_issuer: str
    redis_url: str
    # Maps a presented credential value -> the actor_id recorded in the
    # audit trail for that caller. Currently exactly one entry
    # (nutrition-calculation-service) -- a dict, not a single string, so a
    # future second internal caller doesn't require sharing this one
    # (implementation plan Addendum 2, requirement 1: "a new, distinct
    # per-caller Secrets Manager credential ... not a shared secret").
    reveal_caller_credentials: dict[str, str] = field(default_factory=dict)
    reveal_rate_limit: int = DEFAULT_REVEAL_RATE_LIMIT
    reveal_rate_limit_window_seconds: int = DEFAULT_REVEAL_RATE_LIMIT_WINDOW_SECONDS
    public_port: int = DEFAULT_PUBLIC_PORT
    internal_port: int = DEFAULT_INTERNAL_PORT
    kms_endpoint_url: str | None = None

    @classmethod
    def from_env(cls) -> Settings:
        reveal_credential_nutrition_calc = os.environ.get(
            "PROFILE_SERVICE_REVEAL_CREDENTIAL_NUTRITION_CALC"
        )
        reveal_caller_credentials = (
            {reveal_credential_nutrition_calc: NUTRITION_CALCULATION_SERVICE_ACTOR}
            if reveal_credential_nutrition_calc
            else {}
        )
        return cls(
            database_url=os.environ["PROFILE_SERVICE_DATABASE_URL"],
            rabbitmq_url=os.environ.get(
                "PROFILE_SERVICE_RABBITMQ_URL", "amqp://guest:guest@localhost/"
            ),
            aws_region=os.environ.get("AWS_REGION", "us-east-1"),
            kms_key_id=os.environ["PROFILE_SERVICE_KMS_KEY_ID"],
            kms_endpoint_url=os.environ.get("PROFILE_SERVICE_KMS_ENDPOINT_URL"),
            identity_jwks_url=os.environ.get(
                "PROFILE_SERVICE_IDENTITY_JWKS_URL", DEFAULT_IDENTITY_JWKS_URL
            ),
            identity_issuer=os.environ.get(
                "PROFILE_SERVICE_IDENTITY_ISSUER", DEFAULT_IDENTITY_ISSUER
            ),
            redis_url=os.environ.get("PROFILE_SERVICE_REDIS_URL", "redis://localhost:6379/0"),
            reveal_caller_credentials=reveal_caller_credentials,
            reveal_rate_limit=int(
                os.environ.get("PROFILE_SERVICE_REVEAL_RATE_LIMIT", DEFAULT_REVEAL_RATE_LIMIT)
            ),
            reveal_rate_limit_window_seconds=int(
                os.environ.get(
                    "PROFILE_SERVICE_REVEAL_RATE_LIMIT_WINDOW_SECONDS",
                    DEFAULT_REVEAL_RATE_LIMIT_WINDOW_SECONDS,
                )
            ),
            public_port=int(os.environ.get("PROFILE_SERVICE_PUBLIC_PORT", DEFAULT_PUBLIC_PORT)),
            internal_port=int(
                os.environ.get("PROFILE_SERVICE_INTERNAL_PORT", DEFAULT_INTERNAL_PORT)
            ),
        )


class Container:
    """Holds long-lived infrastructure clients (DB engine, KMS client,
    RabbitMQ) and request-scoped factories for repositories/handlers."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

        # Dedicated engine/pool for audit writes -- every connection it
        # hands out runs `SET ROLE profile_service_audit_writer` at the
        # Postgres protocol level (asyncpg server_settings, applied at
        # connection start), so the audit repository is genuinely
        # restricted to INSERT-only on audit_records for the lifetime of
        # that connection (observability-audit SKILL.md, CLAUDE.md §2.8).
        # Deliberately a separate engine/session from `self.engine`, not
        # just a role switch on a shared session -- an audit write must
        # never silently downgrade (or be downgraded by) the privilege of
        # whatever else that shared session/transaction is doing. Exact
        # same pattern as identity-service's Container.audit_engine.
        self.audit_engine: AsyncEngine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            connect_args={"server_settings": {"role": AUDIT_WRITER_ROLE}},
        )
        self.audit_session_factory = async_sessionmaker(self.audit_engine, expire_on_commit=False)

        # Bulkhead (resilience-patterns SKILL.md): the reveal-metrics
        # endpoint's Redis rate limiter gets its own client/connection
        # pool, independent of anything else this service does, so a
        # Redis outage's blast radius is scoped to that one endpoint.
        # Explicit, short timeouts -- the limiter fails closed
        # (RedisRateLimiter) on any RedisError including a timeout, so a
        # slow-but-not-dead Redis should fail fast, never hang the caller.
        self.redis = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        self.rate_limiter = RedisRateLimiter(self.redis)

        kms_client = boto3.client(
            "kms",
            region_name=settings.aws_region,
            endpoint_url=settings.kms_endpoint_url,
            # Bounds a SINGLE KMS attempt (connect + read) -- retries are
            # handled entirely by KmsEnvelopeDataEncryption's own tenacity
            # retry, not botocore's, so max_attempts=1 disables botocore's
            # built-in retry to avoid two independent retry layers
            # compounding (resilience-patterns SKILL.md; see
            # kms_envelope_data_encryption.py's "Timeout composition" note).
            config=BotoConfig(
                connect_timeout=DEFAULT_CALL_TIMEOUT_SECONDS,
                read_timeout=DEFAULT_CALL_TIMEOUT_SECONDS,
                retries={"max_attempts": 1},
            ),
        )
        self.encryption = KmsEnvelopeDataEncryption(
            self.session_factory, kms_client, settings.kms_key_id
        )

        # Verifies identity-service-issued access tokens locally via its
        # published JWKS (ADR-0022) -- no synchronous call back to
        # identity-service on every request, only on a JWKS cache miss/
        # expiry. See infrastructure/http/dependencies.py.
        self.jwt_verifier = JwtVerifier(
            jwks_url=settings.identity_jwks_url, issuer=settings.identity_issuer
        )

        self._rabbitmq_connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._event_publisher: RabbitMqEventPublisher | None = None
        self._user_registered_consumer: UserRegisteredConsumer | None = None
        self._outbox_relay_worker: OutboxRelayWorker | None = None
        self._background_tasks: list[asyncio.Task[None]] = []

    async def startup(self) -> None:
        self._rabbitmq_connection = await aio_pika.connect_robust(self.settings.rabbitmq_url)
        self._event_publisher = await RabbitMqEventPublisher.create(self._rabbitmq_connection)

        self._outbox_relay_worker = OutboxRelayWorker(self.session_factory, self._event_publisher)
        self._background_tasks.append(asyncio.create_task(self._outbox_relay_worker.run_forever()))

        self._user_registered_consumer = UserRegisteredConsumer(self.session_factory)
        await self._user_registered_consumer.setup(self._rabbitmq_connection)
        await self._user_registered_consumer.consume()

    async def shutdown(self) -> None:
        for task in self._background_tasks:
            task.cancel()
        for task in self._background_tasks:
            try:
                await task
            except asyncio.CancelledError:
                # Reaping a task WE just cancelled above, not our own
                # cancellation -- swallowing it here is the standard
                # asyncio idiom for "wait for this cancellation to
                # finish"; re-raising would abort shutdown() itself and
                # skip closing the rabbitmq/redis/engine resources below.
                pass
            except Exception:
                logger.exception("background_task_shutdown_error")
        if self._rabbitmq_connection is not None:
            await self._rabbitmq_connection.close()
        await self.redis.aclose()
        await self.audit_engine.dispose()
        await self.engine.dispose()

    @property
    def event_publisher(self) -> RabbitMqEventPublisher:
        if self._event_publisher is None:
            raise RuntimeError("Container.startup() must be awaited before use.")
        return self._event_publisher

    def new_session(self) -> AsyncSession:
        return self.session_factory()

    def new_audit_session(self) -> AsyncSession:
        """Separate session bound to Container.audit_engine
        (privilege-restricted via SET ROLE at connect time) -- never share
        this with new_session()'s session (see Container.__init__'s
        audit_engine docstring)."""
        return self.audit_session_factory()
