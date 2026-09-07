"""VectorStorePort -- the vector-store adapter boundary
(.claude/agents/nutrition-assistant-agent.md: "the vector store (Qdrant)
... [is an] adapter behind VectorStorePort"). Scoped to a single named
collection per call -- never a cross-collection query, per
rag-conventions SKILL.md's "never mix content types with different
access-control requirements in the same collection" rule. Concrete
adapter: infrastructure.vectorstore.qdrant_vector_store_adapter.QdrantVectorStoreAdapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class VectorStoreUnavailableError(Exception):
    """Raised on circuit-open or a persistent Qdrant failure. Callers must
    fall back to structured-data-only grounding (implementation plan
    section 7), never a hard failure of the whole chat endpoint."""


@dataclass(frozen=True, slots=True)
class VectorStorePoint:
    point_id: str
    vector: list[float]
    payload: dict[str, str]


@dataclass(frozen=True, slots=True)
class VectorStoreHit:
    point_id: str
    score: float
    payload: dict[str, str]


class VectorStorePort(Protocol):
    async def upsert(self, collection: str, points: list[VectorStorePoint]) -> None: ...

    async def search(
        self, collection: str, query_vector: list[float], top_k: int
    ) -> list[VectorStoreHit]: ...

    async def exists(self, collection: str, point_id: str) -> bool:
        """Used by infrastructure/vectorstore/seed_knowledge_base.py to
        make re-seeding incremental: a point whose deterministic,
        content-derived ID already exists is never re-embedded/re-upserted
        (test plan section 3's incremental re-seed requirement)."""
        ...
