"""Real (testcontainers Qdrant + real LocalEmbeddingAdapter, wrapped with
a call-counting spy) test of the incremental re-seed requirement (test
plan section 3): re-running seed_knowledge_base against an unchanged
corpus makes zero new embed calls; adding one new file embeds only that
file."""

from __future__ import annotations

import os
import shutil

import pytest

from infrastructure.vectorstore.local_embedding_adapter import LocalEmbeddingAdapter
from infrastructure.vectorstore.qdrant_vector_store_adapter import QdrantVectorStoreAdapter
from infrastructure.vectorstore.seed_knowledge_base import seed_knowledge_base

COLLECTION = "test_knowledge_base_incremental"


class _CountingEmbeddingSpy:
    def __init__(self, delegate: LocalEmbeddingAdapter) -> None:
        self._delegate = delegate
        self.embed_call_count = 0

    async def embed(self, text: str) -> list[float]:
        self.embed_call_count += 1
        return await self._delegate.embed(text)

    @property
    def model_name(self) -> str:
        return self._delegate.model_name

    @property
    def dimensions(self) -> int:
        return self._delegate.dimensions


@pytest.fixture
async def vector_store(qdrant_url: str):
    embedding = LocalEmbeddingAdapter()
    adapter = QdrantVectorStoreAdapter(url=qdrant_url, vector_size=embedding.dimensions)
    try:
        yield adapter
    finally:
        await adapter.aclose()


@pytest.fixture
def seed_corpus(tmp_path):
    src_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "knowledge_base",
        "seed",
    )
    dest_dir = tmp_path / "seed"
    shutil.copytree(src_dir, dest_dir)
    return dest_dir


async def test_first_run_embeds_every_file(vector_store, seed_corpus) -> None:
    embedding = _CountingEmbeddingSpy(LocalEmbeddingAdapter())
    file_count = len(list(seed_corpus.glob("*.md")))
    result = await seed_knowledge_base(str(seed_corpus), COLLECTION, vector_store, embedding)
    assert result["embedded"] == file_count
    assert embedding.embed_call_count == file_count


async def test_second_run_unchanged_corpus_embeds_nothing(vector_store, seed_corpus) -> None:
    embedding = _CountingEmbeddingSpy(LocalEmbeddingAdapter())
    await seed_knowledge_base(str(seed_corpus), COLLECTION, vector_store, embedding)
    embed_calls_after_first_run = embedding.embed_call_count

    result_second_run = await seed_knowledge_base(
        str(seed_corpus), COLLECTION, vector_store, embedding
    )

    assert result_second_run["embedded"] == 0
    assert embedding.embed_call_count == embed_calls_after_first_run  # zero new calls


async def test_adding_one_new_file_embeds_only_that_file(vector_store, seed_corpus) -> None:
    embedding = _CountingEmbeddingSpy(LocalEmbeddingAdapter())
    await seed_knowledge_base(str(seed_corpus), COLLECTION, vector_store, embedding)
    calls_before = embedding.embed_call_count

    new_file = seed_corpus / "what_is_a_new_fact.md"
    new_file.write_text(
        "STATUS: DRAFT — pending human/professional review before production use\n"
        "Topic: a brand new fact added incrementally\n\nThis is a new fact."
    )

    result = await seed_knowledge_base(str(seed_corpus), COLLECTION, vector_store, embedding)

    assert result["embedded"] == 1
    assert embedding.embed_call_count == calls_before + 1
