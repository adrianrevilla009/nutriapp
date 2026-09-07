"""QdrantVectorStoreAdapter -- implements VectorStorePort using Qdrant's
async client (.claude/agents/nutrition-assistant-agent.md: "the vector
store (Qdrant) [is an] adapter behind VectorStorePort").

Own DEDICATED purgatory circuit breaker (qdrant_search) -- resilience-
patterns SKILL.md mandates one per external/synchronous-outbound
dependency; this is a genuine addition beyond what implementation plan
section 7 spelled out explicitly (which only names the LLM-call breaker),
added here for consistency with that skill's blanket rule -- flagged for
architecture-agent review as a plan-vs-skill reconciliation, not a
silent scope expansion.

Point-ID determinism (test plan section 3's "embedding pipeline
determinism/idempotency" requirement): a point's ID is a UUID5 derived
from (collection, content) -- the SAME content upserted twice, even in
two separate process runs, always resolves to the SAME point ID, so a
second upsert overwrites in place rather than creating a duplicate point.
This is what makes infrastructure/vectorstore/seed_knowledge_base.py's
re-seed idempotent without needing its own separate dedup bookkeeping."""

from __future__ import annotations

import uuid

import purgatory
from purgatory.domain.model import OpenedState
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from domain.ports.vector_store_port import (
    VectorStoreHit,
    VectorStorePoint,
    VectorStoreUnavailableError,
)

CIRCUIT_NAME = "qdrant_search"
DEFAULT_FAIL_MAX = 5
DEFAULT_RESET_TIMEOUT_SECONDS = 30
POINT_ID_NAMESPACE = uuid.UUID("6f2b1a2e-6e2b-4a52-9f2e-8e6a4f8f9d3b")


def deterministic_point_id(collection: str, content: str) -> str:
    """Same (collection, content) pair -> same UUID5, every time, in every
    process -- the idempotency guarantee test plan section 3 requires."""
    return str(uuid.uuid5(POINT_ID_NAMESPACE, f"{collection}:{content}"))


class QdrantVectorStoreAdapter:
    """Implements domain.ports.vector_store_port.VectorStorePort."""

    def __init__(
        self,
        url: str,
        vector_size: int,
        api_key: str | None = None,
        fail_max: int = DEFAULT_FAIL_MAX,
        reset_timeout_seconds: float = DEFAULT_RESET_TIMEOUT_SECONDS,
        client: AsyncQdrantClient | None = None,
    ) -> None:
        self._client = client or AsyncQdrantClient(url=url, api_key=api_key, timeout=10)
        self._vector_size = vector_size
        self._breaker_factory = purgatory.AsyncCircuitBreakerFactory(
            default_threshold=fail_max, default_ttl=reset_timeout_seconds
        )

    async def ensure_collection(self, collection: str) -> None:
        exists = await self._client.collection_exists(collection)
        if not exists:
            await self._client.create_collection(
                collection_name=collection,
                vectors_config=qdrant_models.VectorParams(
                    size=self._vector_size, distance=qdrant_models.Distance.COSINE
                ),
            )

    async def upsert(self, collection: str, points: list[VectorStorePoint]) -> None:
        await self.ensure_collection(collection)
        qdrant_points = [
            qdrant_models.PointStruct(id=p.point_id, vector=p.vector, payload=p.payload)
            for p in points
        ]
        await self._client.upsert(collection_name=collection, points=qdrant_points)

    async def search(
        self, collection: str, query_vector: list[float], top_k: int
    ) -> list[VectorStoreHit]:
        breaker = await self._breaker_factory.get_breaker(CIRCUIT_NAME)
        try:
            async with breaker:
                if not await self._client.collection_exists(collection):
                    return []
                results = await self._client.query_points(
                    collection_name=collection, query=query_vector, limit=top_k
                )
        except OpenedState as exc:
            raise VectorStoreUnavailableError("Qdrant search circuit is open.") from exc
        except (ResponseHandlingException, UnexpectedResponse) as exc:
            raise VectorStoreUnavailableError(f"Qdrant search failed: {exc}") from exc

        return [
            VectorStoreHit(
                point_id=str(point.id), score=point.score, payload=dict(point.payload or {})
            )
            for point in results.points
        ]

    async def exists(self, collection: str, point_id: str) -> bool:
        if not await self._client.collection_exists(collection):
            return False
        results = await self._client.retrieve(collection_name=collection, ids=[point_id])
        return len(results) > 0

    async def aclose(self) -> None:
        await self._client.close()
