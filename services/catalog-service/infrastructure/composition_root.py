"""Composition root — the only place concrete adapters are wired to the
ports they satisfy (hexagonal-architecture SKILL.md). Route handlers and
the outbox relay worker depend on this module, never the reverse. Mirrors
services/identity-service/infrastructure/composition_root.py's shape —
this is the second service to validate that shape under conventional
persistence (implementation plan section 6)."""

from __future__ import annotations

import os
from dataclasses import dataclass

import aio_pika
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from infrastructure.caching.redis_search_cache import RedisSearchCache
from infrastructure.external.usda_fdc.circuit_breaker import UsdaFdcCircuitBreaker
from infrastructure.external.usda_fdc.usda_fdc_client import UsdaFdcClient
from infrastructure.messaging.rabbitmq_event_publisher import RabbitMqEventPublisher
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository
from infrastructure.persistence.postgres_product_repository import PostgresProductRepository
from infrastructure.persistence.postgres_search_read_model import PostgresSearchReadModel


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    redis_url: str
    rabbitmq_url: str
    usda_fdc_api_key: str
    # Checked against the internal `GET /internal/v1/catalog/lookup` route's
    # `X-Internal-Service-Credential` header (implementation plan Addendum
    # 2), consumed by food-recognition-service. Not routed through Kong.
    # No default — a Terraform-managed per-caller secret
    # (infra/terraform/modules/secrets), never checked in; missing means
    # fail closed (KeyError), same as identity-service's
    # internal_reveal_credential, not a silent fallback to a known value.
    internal_lookup_credential: str
    usda_fdc_base_url: str = "https://api.nal.usda.gov/fdc/v1"

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            database_url=os.environ["CATALOG_SERVICE_DATABASE_URL"],
            redis_url=os.environ.get("CATALOG_SERVICE_REDIS_URL", "redis://localhost:6379/1"),
            rabbitmq_url=os.environ.get(
                "CATALOG_SERVICE_RABBITMQ_URL", "amqp://guest:guest@localhost/"
            ),
            usda_fdc_api_key=os.environ.get("CATALOG_SERVICE_USDA_FDC_API_KEY", "DEMO_KEY"),
            usda_fdc_base_url=os.environ.get(
                "CATALOG_SERVICE_USDA_FDC_BASE_URL", "https://api.nal.usda.gov/fdc/v1"
            ),
            internal_lookup_credential=os.environ["CATALOG_INTERNAL_LOOKUP_CREDENTIAL"],
        )


class Container:
    """Holds long-lived infrastructure clients (DB engine, Redis,
    RabbitMQ) and request-scoped factories for repositories/handlers."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        self.redis = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        self.search_cache = RedisSearchCache(self.redis)
        self.usda_fdc_client = UsdaFdcClient(
            redis=self.redis,
            api_key=settings.usda_fdc_api_key,
            base_url=settings.usda_fdc_base_url,
        )
        self.usda_fdc_circuit_breaker = UsdaFdcCircuitBreaker()
        self._rabbitmq_connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._event_publisher: RabbitMqEventPublisher | None = None

    async def startup(self) -> None:
        self._rabbitmq_connection = await aio_pika.connect_robust(self.settings.rabbitmq_url)
        self._event_publisher = await RabbitMqEventPublisher.create(self._rabbitmq_connection)

    async def shutdown(self) -> None:
        if self._rabbitmq_connection is not None:
            await self._rabbitmq_connection.close()
        await self.usda_fdc_client.aclose()
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
) -> tuple[PostgresProductRepository, PostgresOutboxRepository, PostgresSearchReadModel]:
    """Convenience bundle of the request-scoped repository adapters —
    product/outbox share one AsyncSession (and therefore one DB
    transaction) for outbox atomicity, same convention as
    identity-service's build_repositories."""
    return (
        PostgresProductRepository(session),
        PostgresOutboxRepository(session),
        PostgresSearchReadModel(session),
    )
