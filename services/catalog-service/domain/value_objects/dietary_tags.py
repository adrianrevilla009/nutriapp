"""DietaryTag enum + DietaryTags value object."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum


class DietaryTag(str, Enum):
    VEGAN = "vegan"
    VEGETARIAN = "vegetarian"
    GLUTEN_FREE = "gluten_free"
    LACTOSE_FREE = "lactose_free"
    ORGANIC = "organic"
    LOW_SUGAR = "low_sugar"
    LOW_SODIUM = "low_sodium"
    KETO = "keto"
    HALAL = "halal"
    KOSHER = "kosher"


@dataclass(frozen=True, slots=True)
class DietaryTags:
    tags: frozenset[DietaryTag]

    @classmethod
    def empty(cls) -> DietaryTags:
        return cls(frozenset())

    @classmethod
    def from_raw_labels(cls, raw_labels: list[str]) -> DietaryTags:
        """Constructs from a raw label list: dedups and normalizes case; an
        unrecognized raw label is dropped, not raised — a single unknown
        label must never block cataloguing (test-plan §1)."""
        normalized: set[DietaryTag] = set()
        for raw in raw_labels:
            candidate = raw.strip().lower().replace("-", "_").replace(" ", "_")
            try:
                normalized.add(DietaryTag(candidate))
            except ValueError:
                continue
        return cls(frozenset(normalized))

    @classmethod
    def union(cls, *tag_sets: DietaryTags) -> DietaryTags:
        merged: frozenset[DietaryTag] = frozenset()
        for tag_set in tag_sets:
            merged = merged | tag_set.tags
        return cls(merged)

    def __contains__(self, tag: DietaryTag) -> bool:
        return tag in self.tags

    def __iter__(self) -> Iterator[DietaryTag]:
        return iter(sorted(self.tags, key=lambda t: t.value))
