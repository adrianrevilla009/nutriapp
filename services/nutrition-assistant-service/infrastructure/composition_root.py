"""Composition root -- the only place concrete adapters are wired to the
ports they satisfy (hexagonal-architecture SKILL.md). The HTTP route and
all three consumers depend on this module, never the reverse.

NOTE (implementation plan section 9, flagged deviation -- see README.md
"Known gaps"): this service consumes billing-service's EntitlementGranted/
Revoked... actually it does NOT in this pass -- entitlement_cache has no
live writer (no billing_events_consumer.py exists, unlike recipe-service/
social-service/analytics-service's fourth consumer). Every chat request
therefore falls through to the synchronous EntitlementCheckPort call via
application.entitlement_check.is_user_entitled -- safe (never
stale-positive) but forgoes the cache's latency/load-reduction purpose.
Flagged for a fast-follow, not fixed here (out of the approved plan's
file list)."""

from __future__ import annotations

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
from infrastructure.external.claude_conversation_adapter import ClaudeConversationAdapter
from infrastructure.messaging.analytics_events_consumer import AnalyticsEventsConsumer
from infrastructure.messaging.diary_events_consumer import DiaryEventsConsumer
from infrastructure.messaging.nutrition_calculation_events_consumer import (
    NutritionCalculationEventsConsumer,
)
from infrastructure.messaging.resilient_topic_consumer import ResilientTopicConsumer
from infrastructure.persistence.postgres_analytics_signals_repository import (
    PostgresAnalyticsSignalsRepository,
)
from infrastructure.persistence.postgres_chat_audit_repository import PostgresChatAuditRepository
from infrastructure.persistence.postgres_diary_history_repository import (
    PostgresDiaryHistoryRepository,
)
from infrastructure.persistence.postgres_entitlement_cache_repository import (
    PostgresEntitlementCacheRepository,
)
from infrastructure.persistence.postgres_nutrition_history_repository import (
    PostgresNutritionHistoryRepository,
)
from infrastructure.vectorstore.local_embedding_adapter import LocalEmbeddingAdapter
from infrastructure.vectorstore.qdrant_vector_store_adapter import QdrantVectorStoreAdapter

logger = structlog.get_logger()

DEFAULT_IDENTITY_JWKS_URL = "http://identity-service:8000/.well-known/jwks.json"
DEFAULT_IDENTITY_ISSUER = "identity-service"
DEFAULT_BILLING_SERVICE_BASE_URL = "http://billing-service:8000"
DEFAULT_QDRANT_URL = "http://nutrition-assistant-qdrant:6333"
DEFAULT_KNOWLEDGE_BASE_COLLECTION = "nutrition_assistant_knowledge_base"


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    rabbitmq_url: str
    identity_jwks_url: str
    identity_issuer: str
    billing_service_base_url: str
    billing_entitlement_credential: str
    anthropic_api_key: str
    conversation_model: str
    qdrant_url: str
    knowledge_base_collection: str

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            database_url=os.environ["NUTRITION_ASSISTANT_SERVICE_DATABASE_URL"],
            rabbitmq_url=os.environ.get(
                "NUTRITION_ASSISTANT_SERVICE_RABBITMQ_URL", "amqp://guest:guest@localhost/"
            ),
            identity_jwks_url=os.environ.get(
                "NUTRITION_ASSISTANT_SERVICE_IDENTITY_JWKS_URL", DEFAULT_IDENTITY_JWKS_URL
            ),
            identity_issuer=os.environ.get(
                "NUTRITION_ASSISTANT_SERVICE_IDENTITY_ISSUER", DEFAULT_IDENTITY_ISSUER
            ),
            billing_service_base_url=os.environ.get(
                "NUTRITION_ASSISTANT_SERVICE_BILLING_SERVICE_BASE_URL",
                DEFAULT_BILLING_SERVICE_BASE_URL,
            ),
            billing_entitlement_credential=os.environ.get(
                "NUTRITION_ASSISTANT_SERVICE_BILLING_ENTITLEMENT_CREDENTIAL",
                "local-dev-billing-entitlement-credential-change-me",
            ),
            anthropic_api_key=os.environ.get("NUTRITION_ASSISTANT_SERVICE_ANTHROPIC_API_KEY", ""),
            conversation_model=os.environ.get(
                "NUTRITION_ASSISTANT_SERVICE_CONVERSATION_MODEL", "claude-haiku-4-5"
            ),
            qdrant_url=os.environ.get("NUTRITION_ASSISTANT_SERVICE_QDRANT_URL", DEFAULT_QDRANT_URL),
            knowledge_base_collection=os.environ.get(
                "NUTRITION_ASSISTANT_SERVICE_KNOWLEDGE_BASE_COLLECTION",
                DEFAULT_KNOWLEDGE_BASE_COLLECTION,
            ),
        )


class Container:
    """Holds long-lived infrastructure clients and request-scoped factories.
    Starts all three topic consumers as background tasks (analytics-service's
    precedent). The outbox relay worker is NOT started this pass -- no live
    publisher exists yet (implementation plan section 5)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

        self.jwt_verifier = JwtVerifier(
            jwks_url=settings.identity_jwks_url, issuer=settings.identity_issuer
        )

        self.entitlement_check = BillingEntitlementClient(
            base_url=settings.billing_service_base_url,
            credential=settings.billing_entitlement_credential,
        )

        self.conversation = ClaudeConversationAdapter(
            api_key=settings.anthropic_api_key, model=settings.conversation_model
        )
        self.embedding = LocalEmbeddingAdapter()
        self.vector_store = QdrantVectorStoreAdapter(
            url=settings.qdrant_url, vector_size=self.embedding.dimensions
        )

        self._rabbitmq_connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._consumers: list[ResilientTopicConsumer] = []

    async def _start_consumer(self, consumer: ResilientTopicConsumer) -> None:
        assert self._rabbitmq_connection is not None
        await consumer.setup(self._rabbitmq_connection)
        await consumer.consume()
        self._consumers.append(consumer)

    async def startup(self) -> None:
        self._rabbitmq_connection = await aio_pika.connect_robust(self.settings.rabbitmq_url)
        await self._start_consumer(DiaryEventsConsumer(self.session_factory))
        await self._start_consumer(NutritionCalculationEventsConsumer(self.session_factory))
        await self._start_consumer(AnalyticsEventsConsumer(self.session_factory))

    async def shutdown(self) -> None:
        if self._rabbitmq_connection is not None:
            await self._rabbitmq_connection.close()
        await self.entitlement_check.aclose()
        await self.conversation.aclose()
        await self.vector_store.aclose()
        await self.engine.dispose()

    def new_session(self) -> AsyncSession:
        return self.session_factory()


def build_repositories(
    session: AsyncSession,
) -> tuple[
    PostgresDiaryHistoryRepository,
    PostgresNutritionHistoryRepository,
    PostgresAnalyticsSignalsRepository,
    PostgresEntitlementCacheRepository,
    PostgresChatAuditRepository,
]:
    """Convenience bundle of the request-scoped repository adapters used by
    the HTTP route -- every repository shares one AsyncSession (and
    therefore one DB transaction), same convention as every other
    service's `build_repositories`."""
    return (
        PostgresDiaryHistoryRepository(session),
        PostgresNutritionHistoryRepository(session),
        PostgresAnalyticsSignalsRepository(session),
        PostgresEntitlementCacheRepository(session),
        PostgresChatAuditRepository(session),
    )
