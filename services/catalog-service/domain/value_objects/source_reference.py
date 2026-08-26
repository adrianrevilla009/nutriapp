"""SourceReference value object — which third-party source contributed a
given raw record, and that source's own product id/URL, for
`product_sources` audit tracking (implementation plan §7)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SourceName(str, Enum):
    OPEN_FOOD_FACTS = "open_food_facts"
    USDA_FDC = "usda_fdc"


@dataclass(frozen=True, slots=True)
class SourceReference:
    source: SourceName
    source_product_id: str
    last_seen_at: datetime
