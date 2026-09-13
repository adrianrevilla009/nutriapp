"""Composition root -- the only place concrete adapters are wired to the
ports they satisfy (hexagonal-architecture SKILL.md). Route handlers and
the outbox relay worker depend on this module, never the reverse. Mirrors
services/catalog-service/infrastructure/composition_root.py's shape --
event-driven CRUD, conventional persistence, no caching layer needed
(implementation plan section 7).

**Fitbit feature-flag gate** (`/plans/activity-service/implementation-plan.md`'s
2026-09-11 addendum, `/plans/activity-service/test-plan.md`'s matching
addendum section 4): `Container.fitbit_provider` is the ONLY way any other
code in this service can obtain a `FitbitProviderAdapter`, and it refuses
to construct one -- raising `WearableSyncDisabledError` -- unless BOTH
`wearable_sync_enabled` is `True` AND real-looking Fitbit OAuth client
credentials are configured. No real Fitbit developer account exists in
this environment today, so in every real deployment of this repo as of
this addendum, that property raises by construction -- there is no
credential-independent way to silently activate wearable sync.

A full Unleash SDK integration (`.claude/skills/feature-flags/SKILL.md`)
is deferred until `packages/feature-flags-client` exists (no service in
this repo wires Unleash yet, same deferral as
`food-recognition-service`'s `photo_analysis_enabled` flag) -- this
env-var-based flag has the same boolean-gate shape and is a drop-in swap
later, documented in README.md.
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

from infrastructure.external.fitbit_provider_adapter import FitbitProviderAdapter
from infrastructure.external.in_memory_wearable_token_store import InMemoryWearableTokenStore
from infrastructure.messaging.rabbitmq_event_publisher import RabbitMqEventPublisher
from infrastructure.persistence.postgres_exercise_repository import PostgresExerciseRepository
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository


class WearableSyncDisabledError(Exception):
    """Raised by `Container.fitbit_provider` when the
    `ACTIVITY_SERVICE_WEARABLE_SYNC_ENABLED` flag is off, or when it is on
    but no real Fitbit OAuth client credentials are configured -- either
    condition alone is sufficient to refuse construction. Never caught and
    silently ignored by any caller; a caller that wants to offer wearable
    sync must handle this explicitly (e.g. surface "not available yet" to
    the user), never fall back to a degraded-but-live Fitbit call."""


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
    # Feature flag (implementation plan addendum 2026-09-11, acceptance
    # criterion: "wired behind an explicit config/feature-flag toggle...
    # so it cannot be silently activated without real credentials being
    # configured later"). Defaults to False/empty in every environment
    # until a human provisions a real Fitbit developer account.
    wearable_sync_enabled: bool = False
    fitbit_client_id: str = ""
    fitbit_client_secret: str = ""
    fitbit_redirect_uri: str = ""

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
            wearable_sync_enabled=_bool_env("ACTIVITY_SERVICE_WEARABLE_SYNC_ENABLED", False),
            fitbit_client_id=os.environ.get("ACTIVITY_SERVICE_FITBIT_CLIENT_ID", ""),
            fitbit_client_secret=os.environ.get("ACTIVITY_SERVICE_FITBIT_CLIENT_SECRET", ""),
            fitbit_redirect_uri=os.environ.get("ACTIVITY_SERVICE_FITBIT_REDIRECT_URI", ""),
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
        # Process-local, non-persistent token store (see that module's
        # docstring for why a durable, encrypted-at-rest store is deferred).
        # Constructed unconditionally -- it is inert with no adapter using
        # it while wearable sync is disabled/unconfigured.
        self._wearable_token_store = InMemoryWearableTokenStore()
        self._fitbit_provider: FitbitProviderAdapter | None = None

    async def startup(self) -> None:
        self._rabbitmq_connection = await aio_pika.connect_robust(self.settings.rabbitmq_url)
        self._event_publisher = await RabbitMqEventPublisher.create(self._rabbitmq_connection)

    async def shutdown(self) -> None:
        if self._rabbitmq_connection is not None:
            await self._rabbitmq_connection.close()
        if self._fitbit_provider is not None:
            await self._fitbit_provider.aclose()
        await self.engine.dispose()

    @property
    def fitbit_provider(self) -> FitbitProviderAdapter:
        """Lazily constructs (and caches) the sole `FitbitProviderAdapter`
        instance for this `Container`'s lifetime -- raises
        `WearableSyncDisabledError` instead of constructing one whenever
        the feature flag is off OR real-looking credentials are missing,
        per this module's docstring. Never partially wires an adapter with
        empty credentials "just in case" -- either both conditions hold or
        this raises."""
        if not self.settings.wearable_sync_enabled:
            raise WearableSyncDisabledError(
                "Wearable sync is disabled (ACTIVITY_SERVICE_WEARABLE_SYNC_ENABLED is not set)."
            )
        if not self.settings.fitbit_client_id or not self.settings.fitbit_client_secret:
            raise WearableSyncDisabledError(
                "Wearable sync is enabled but no Fitbit OAuth client credentials are configured."
            )
        if self._fitbit_provider is None:
            self._fitbit_provider = FitbitProviderAdapter(
                client_id=self.settings.fitbit_client_id,
                client_secret=self.settings.fitbit_client_secret,
                redirect_uri=self.settings.fitbit_redirect_uri,
                token_store=self._wearable_token_store,
            )
        return self._fitbit_provider

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
