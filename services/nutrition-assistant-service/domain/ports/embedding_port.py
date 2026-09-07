"""EmbeddingPort -- the embedding-model adapter boundary. Concrete
adapter: infrastructure.vectorstore.local_embedding_adapter.LocalEmbeddingAdapter
(self-hosted, open-source, no external vendor call -- implementation plan
section 9 resolution 1)."""

from __future__ import annotations

from typing import Protocol


class EmbeddingPort(Protocol):
    async def embed(self, text: str) -> list[float]: ...

    @property
    def model_name(self) -> str: ...

    @property
    def dimensions(self) -> int: ...
