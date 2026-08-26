"""Parses a recorded sample OFF export file end-to-end — never a live
request (external-data-ethics SKILL.md / test-plan section 2)."""

from __future__ import annotations

import os

from infrastructure.external.open_food_facts.open_food_facts_source_adapter import (
    OpenFoodFactsSourceAdapter,
)

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "fixtures",
    "open_food_facts_export_samples",
    "sample_export.jsonl",
)


async def test_parses_sample_export_including_malformed_row_skipped():
    adapter = OpenFoodFactsSourceAdapter(FIXTURE_PATH, batch_size=10)

    batch = await adapter.fetch_batch(None)

    # 4 lines total: 2 well-formed, 1 malformed JSON, 1 missing identifier.
    assert len(batch.records) == 2
    assert batch.skipped_count == 2
    assert batch.next_cursor is None
    names = {r.name for r in batch.records}
    assert "Organic Oat Milk" in names
    assert "Whole Wheat Bread" in names


async def test_pages_through_small_batch_size():
    adapter = OpenFoodFactsSourceAdapter(FIXTURE_PATH, batch_size=1)

    first = await adapter.fetch_batch(None)
    assert len(first.records) == 1
    assert first.next_cursor == "1"

    second = await adapter.fetch_batch(first.next_cursor)
    assert len(second.records) == 1
