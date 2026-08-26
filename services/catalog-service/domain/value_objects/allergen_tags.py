"""AllergenTag enum + AllergenTags value object.

Cross-source vocabulary reconciliation (OFF's `allergens_tags` style vs.
USDA's differently-shaped label fields) happens in
domain/services/allergen_tag_deriver.py; this VO is just the validated,
canonical, deduplicated set.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum


class AllergenTag(str, Enum):
    GLUTEN = "gluten"
    MILK = "milk"
    EGGS = "eggs"
    NUTS = "nuts"
    PEANUTS = "peanuts"
    SOY = "soy"
    FISH = "fish"
    SHELLFISH = "shellfish"
    SESAME = "sesame"
    CELERY = "celery"
    MUSTARD = "mustard"
    SULPHITES = "sulphites"
    LUPIN = "lupin"
    MOLLUSCS = "molluscs"


@dataclass(frozen=True, slots=True)
class AllergenTags:
    tags: frozenset[AllergenTag]

    @classmethod
    def empty(cls) -> AllergenTags:
        return cls(frozenset())

    @classmethod
    def union(cls, *tag_sets: AllergenTags) -> AllergenTags:
        """Union, never intersection, of allergen info across sources — a
        deliberate conservative default (test-plan §1: never silently drop
        a safety-relevant allergen tag one source reported)."""
        merged: frozenset[AllergenTag] = frozenset()
        for tag_set in tag_sets:
            merged = merged | tag_set.tags
        return cls(merged)

    def __contains__(self, tag: AllergenTag) -> bool:
        return tag in self.tags

    def __iter__(self) -> Iterator[AllergenTag]:
        return iter(sorted(self.tags, key=lambda t: t.value))
