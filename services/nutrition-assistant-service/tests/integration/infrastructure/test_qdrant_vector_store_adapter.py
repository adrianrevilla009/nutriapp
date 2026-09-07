"""Real (testcontainers) Qdrant test -- test plan section 3's explicit
"embedding pipeline determinism/idempotency" requirement."""

from __future__ import annotations

import pytest

from domain.ports.vector_store_port import VectorStorePoint
from infrastructure.vectorstore.qdrant_vector_store_adapter import (
    QdrantVectorStoreAdapter,
    deterministic_point_id,
)

COLLECTION_A = "test_collection_a"
COLLECTION_B = "test_collection_b"


@pytest.fixture
async def adapter(qdrant_url: str):
    a = QdrantVectorStoreAdapter(url=qdrant_url, vector_size=3)
    try:
        yield a
    finally:
        await a.aclose()


async def test_upsert_then_search_returns_the_point(adapter: QdrantVectorStoreAdapter) -> None:
    point_id = deterministic_point_id(COLLECTION_A, "fiber content")
    await adapter.upsert(
        COLLECTION_A,
        [
            VectorStorePoint(
                point_id=point_id, vector=[1.0, 0.0, 0.0], payload={"content": "fiber content"}
            )
        ],
    )
    hits = await adapter.search(COLLECTION_A, [1.0, 0.0, 0.0], top_k=3)
    assert any(h.point_id == point_id for h in hits)


async def test_upserting_same_content_twice_never_duplicates(
    adapter: QdrantVectorStoreAdapter,
) -> None:
    content = "what is a calorie -- a unit of energy"
    point_id = deterministic_point_id(COLLECTION_A, content)

    await adapter.upsert(
        COLLECTION_A,
        [VectorStorePoint(point_id=point_id, vector=[0.5, 0.5, 0.0], payload={"content": content})],
    )
    await adapter.upsert(
        COLLECTION_A,
        [VectorStorePoint(point_id=point_id, vector=[0.5, 0.5, 0.0], payload={"content": content})],
    )

    hits = await adapter.search(COLLECTION_A, [0.5, 0.5, 0.0], top_k=100)
    matching = [h for h in hits if h.point_id == point_id]
    assert len(matching) == 1  # never duplicated


async def test_different_content_produces_a_distinct_point_id(
    adapter: QdrantVectorStoreAdapter,
) -> None:
    id_1 = deterministic_point_id(COLLECTION_A, "content one")
    id_2 = deterministic_point_id(COLLECTION_A, "content two")
    assert id_1 != id_2


async def test_search_is_scoped_to_a_single_collection(adapter: QdrantVectorStoreAdapter) -> None:
    point_id = deterministic_point_id(COLLECTION_B, "only in collection B")
    await adapter.upsert(
        COLLECTION_B,
        [
            VectorStorePoint(
                point_id=point_id, vector=[0.1, 0.2, 0.3], payload={"content": "b-only"}
            )
        ],
    )
    hits_in_a = await adapter.search(COLLECTION_A, [0.1, 0.2, 0.3], top_k=100)
    assert all(h.point_id != point_id for h in hits_in_a)


async def test_exists_reflects_upsert_state(adapter: QdrantVectorStoreAdapter) -> None:
    content = "exists-check content"
    point_id = deterministic_point_id(COLLECTION_A, content)
    assert await adapter.exists(COLLECTION_A, point_id) is False

    await adapter.upsert(
        COLLECTION_A,
        [VectorStorePoint(point_id=point_id, vector=[0.2, 0.2, 0.2], payload={"content": content})],
    )
    assert await adapter.exists(COLLECTION_A, point_id) is True
