"""BulkExportReader — streams/parses a downloaded Open Food Facts JSONL
export file. No live HTTP calls at all (implementation plan section 4):
this adapter only ever reads a file already present on disk.

Malformed lines (unparsable JSON) are skipped-and-counted, never raised
up as a hard failure for the whole batch (external-data-ethics SKILL.md's
"source fragility" guidance / test-plan section 2).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BulkExportReadResult:
    records: tuple[dict[str, Any], ...]
    skipped_count: int
    next_offset: int | None


class BulkExportReader:
    def __init__(self, file_path: str) -> None:
        self._file_path = file_path

    def read_batch(self, offset: int, batch_size: int) -> BulkExportReadResult:
        records: list[dict[str, Any]] = []
        skipped = 0
        with open(self._file_path, encoding="utf-8") as handle:
            for _ in range(offset):
                if not handle.readline():
                    return BulkExportReadResult(records=(), skipped_count=0, next_offset=None)

            read_count = 0
            while read_count < batch_size:
                line = handle.readline()
                if not line:
                    break
                stripped = line.strip()
                read_count += 1
                if not stripped:
                    continue
                try:
                    records.append(json.loads(stripped))
                except json.JSONDecodeError:
                    skipped += 1

            has_more = bool(handle.readline())
            next_offset = offset + read_count if has_more else None

        return BulkExportReadResult(
            records=tuple(records), skipped_count=skipped, next_offset=next_offset
        )
