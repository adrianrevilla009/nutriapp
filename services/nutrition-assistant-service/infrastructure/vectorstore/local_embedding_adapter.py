"""LocalEmbeddingAdapter -- implements EmbeddingPort using a self-hosted,
open-source embedding model. NO external vendor call, NO new
vendor/DPA entry (implementation plan section 9 resolution 1).

Model choice: `sentence-transformers/all-MiniLM-L6-v2`
(Apache-2.0 license, 384 dimensions), run via `fastembed` (ONNX Runtime
backend -- lighter footprint than a torch-based sentence-transformers
install, and it is the same library qdrant-client's own examples use,
keeping this service's two Qdrant-adjacent dependencies aligned). This is
a small, well-established, widely-used sentence-embedding model -- see
README.md "Embedding model" section for the verification of this choice
(name, license, dimensionality) required by implementation plan section 9
resolution 1.

Determinism: the same input text always yields the same embedding vector
(verified in tests/integration/infrastructure/test_local_embedding_adapter.py)
-- relied upon by QdrantVectorStoreAdapter's content-hash-derived point-ID
idempotency scheme (test plan section 3)."""

from __future__ import annotations

import asyncio

DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_LICENSE = "apache-2.0"
MODEL_DIMENSIONS = 384


class LocalEmbeddingAdapter:
    """Implements domain.ports.embedding_port.EmbeddingPort."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        # fastembed's TextEmbedding is a synchronous, CPU-bound (ONNX
        # Runtime) object -- loaded once per adapter instance, never
        # reloaded per call (README.md / test plan section 3's resource-
        # usage sanity requirement).
        from fastembed import TextEmbedding

        self._model_name = model_name
        self._model = TextEmbedding(model_name=model_name)

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return MODEL_DIMENSIONS

    async def embed(self, text: str) -> list[float]:
        # fastembed's .embed() is synchronous/CPU-bound -- run in a thread
        # so it never blocks the event loop other requests share.
        def _embed_sync() -> list[float]:
            (vector,) = self._model.embed([text])
            return vector.tolist()  # type: ignore[no-any-return]

        return await asyncio.to_thread(_embed_sync)
