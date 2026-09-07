"""Real (no mocking) test of the self-hosted embedding model -- downloads
sentence-transformers/all-MiniLM-L6-v2 via fastembed/ONNX Runtime on first
run (cached afterwards). No network call to any LLM/embedding VENDOR API
-- fastembed downloads model weights from Hugging Face Hub once, then runs
fully locally/offline (implementation plan section 9 resolution 1)."""

from __future__ import annotations

import pytest

from infrastructure.vectorstore.local_embedding_adapter import (
    DEFAULT_MODEL_NAME,
    MODEL_DIMENSIONS,
    MODEL_LICENSE,
    LocalEmbeddingAdapter,
)


@pytest.fixture(scope="module")
def adapter() -> LocalEmbeddingAdapter:
    return LocalEmbeddingAdapter()


def test_model_choice_is_the_documented_one() -> None:
    # A silent model swap would fail this test (README.md documents this
    # exact name/license/dimensionality, per resolution 1).
    assert DEFAULT_MODEL_NAME == "sentence-transformers/all-MiniLM-L6-v2"
    assert MODEL_LICENSE == "apache-2.0"
    assert MODEL_DIMENSIONS == 384


async def test_same_text_embeds_identically(adapter: LocalEmbeddingAdapter) -> None:
    v1 = await adapter.embed("what is fiber")
    v2 = await adapter.embed("what is fiber")
    assert v1 == v2


async def test_different_text_embeds_differently(adapter: LocalEmbeddingAdapter) -> None:
    v1 = await adapter.embed("what is fiber")
    v2 = await adapter.embed("what is a calorie")
    assert v1 != v2


async def test_dimensions_match_declared_value(adapter: LocalEmbeddingAdapter) -> None:
    vector = await adapter.embed("hello")
    assert len(vector) == adapter.dimensions == MODEL_DIMENSIONS


async def test_model_not_reloaded_per_call(adapter: LocalEmbeddingAdapter) -> None:
    model_instance_before = adapter._model
    await adapter.embed("first call")
    await adapter.embed("second call")
    assert adapter._model is model_instance_before
