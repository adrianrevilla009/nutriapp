"""CatalogSourcePort — the multi-source pluggable ingestion abstraction
(implementation plan section 2/section 4). Both a file-based source
(Open Food Facts bulk export) and an HTTP-paginated source (USDA FDC)
satisfy this exact shape with zero changes to the domain normalization/
dedup services — the concrete test of the port abstraction's value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from domain.services.product_normalizer import RawProductRecord


@dataclass(frozen=True, slots=True)
class SourceBatch:
    records: tuple[RawProductRecord, ...]
    next_cursor: str | None
    skipped_count: int = 0


class CatalogSourcePort(Protocol):
    async def fetch_batch(self, cursor: str | None) -> SourceBatch: ...
