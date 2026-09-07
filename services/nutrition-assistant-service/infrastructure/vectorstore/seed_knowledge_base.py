"""seed_knowledge_base -- one-off/re-runnable script that chunks, embeds,
and upserts the curated general-nutrition knowledge base
(knowledge_base/seed/*.md) into Qdrant. NOT a live event consumer -- run
manually/at deploy time, per implementation plan section 1's "the curated
knowledge-base documents are chunked once... and upserted into Qdrant by
content ID -- idempotent on re-run."

Chunking strategy (rag-conventions SKILL.md "Chunking Strategy"): one
seed file = one semantic unit = one chunk. Each file already contains
exactly one self-contained fact/definition (see knowledge_base/seed/*.md's
own file-per-fact convention) -- splitting further would risk splitting a
single fact across two chunks, which the skill explicitly warns against;
splitting less (one giant chunk for the whole corpus) would make
retrieval far less precise. One-file-one-chunk is deliberately simple and
matches this pass's genuinely small (~8-10 entry) corpus (implementation
plan section 9 resolution 2) -- revisit if the corpus grows large enough
that any single file stops being a single semantic unit.

Incremental re-seed (test plan section 3): a file's deterministic point
ID is derived from its content (qdrant_vector_store_adapter.deterministic_point_id).
Before embedding, this script checks VectorStorePort.exists() for that ID
-- an unchanged file is skipped entirely (no embed call, no upsert
call). Only a NEW or CHANGED file triggers a real embed+upsert. This is
what makes re-running this script against an unchanged corpus a fully
idempotent no-op, and adding one new file touch only that file's point."""

from __future__ import annotations

import glob
import os

import structlog

from domain.ports.embedding_port import EmbeddingPort
from domain.ports.vector_store_port import VectorStorePoint, VectorStorePort
from infrastructure.vectorstore.qdrant_vector_store_adapter import deterministic_point_id

logger = structlog.get_logger()


def _read_seed_files(seed_dir: str) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in sorted(glob.glob(os.path.join(seed_dir, "*.md"))):
        with open(path, encoding="utf-8") as f:
            files[path] = f.read()
    return files


async def seed_knowledge_base(
    seed_dir: str,
    collection: str,
    vector_store: VectorStorePort,
    embedding: EmbeddingPort,
) -> dict[str, int]:
    """Returns a small summary dict: {"total": N, "embedded": M, "skipped": N-M}."""
    files = _read_seed_files(seed_dir)
    embedded = 0
    skipped = 0

    for path, content in files.items():
        point_id = deterministic_point_id(collection, content)
        if await vector_store.exists(collection, point_id):
            skipped += 1
            continue

        vector = await embedding.embed(content)
        await vector_store.upsert(
            collection,
            [
                VectorStorePoint(
                    point_id=point_id,
                    vector=vector,
                    payload={"content": content, "source_file": path},
                )
            ],
        )
        embedded += 1
        logger.info("knowledge_base_entry_seeded", source_file=path, point_id=point_id)

    logger.info(
        "knowledge_base_seed_complete", total=len(files), embedded=embedded, skipped=skipped
    )
    return {"total": len(files), "embedded": embedded, "skipped": skipped}
