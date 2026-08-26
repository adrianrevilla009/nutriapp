"""Product aggregate root — identity = product_id (uuid); dedup/merge key
= barcode when present (implementation plan Addendum 1, §9.3).

Conventional persistence, not event-sourced (ADR-0002): this entity is the
`products` table's in-memory shape, not a fold over an event stream.
`ProductCatalogued`/`ProductUpdated` are derived as a side effect of
`Product.merge`, published via the Outbox pattern by the application
layer — this module has zero knowledge of the outbox/messaging.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from domain.value_objects.allergen_tags import AllergenTags
from domain.value_objects.barcode import Barcode
from domain.value_objects.dietary_tags import DietaryTags
from domain.value_objects.nutrient_panel import NutrientPanel
from domain.value_objects.package_size import PackageSize
from domain.value_objects.price import Price
from domain.value_objects.source_reference import SourceName

if TYPE_CHECKING:
    from domain.services.product_normalizer import RawProductRecord

# Fields compared to decide whether a merge actually changed anything
# (and therefore whether `ProductUpdated` should be published at all —
# an event with an empty `changed_fields` list is never published,
# test-plan §3).
_COMPARABLE_FIELDS = (
    "name",
    "brand",
    "category",
    "nutrient_panel",
    "dietary_tags",
    "allergen_tags",
    "package_size",
    "price",
)


class InvalidProductError(ValueError):
    """Raised when neither a barcode nor a name is present — a name-or-
    barcode is the minimum required identity for a catalog entry."""


@dataclass(frozen=True, slots=True)
class Product:
    product_id: uuid.UUID
    barcode: Barcode | None
    name: str | None
    brand: str | None
    category: str | None
    nutrient_panel: NutrientPanel | None
    dietary_tags: DietaryTags
    allergen_tags: AllergenTags
    package_size: PackageSize | None
    price: Price | None
    sources: frozenset[SourceName]
    # Per-source last-seen normalized record — the domain-level mirror of
    # the `product_sources` persistence table (implementation plan §7);
    # no raw source data is ever silently discarded on conflict.
    source_snapshots: Mapping[SourceName, RawProductRecord]
    catalogued_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if self.barcode is None and not self.name:
            raise InvalidProductError(
                "Product requires a barcode or a name as its minimum identity."
            )

    @classmethod
    def from_first_record(cls, product_id: uuid.UUID, record: RawProductRecord) -> Product:
        return cls(
            product_id=product_id,
            barcode=record.barcode,
            name=record.name,
            brand=record.brand,
            category=record.category,
            nutrient_panel=record.nutrient_panel,
            dietary_tags=record.dietary_tags,
            allergen_tags=record.allergen_tags,
            package_size=record.package_size,
            price=record.price,
            sources=frozenset({record.source}),
            source_snapshots={record.source: record},
            catalogued_at=record.observed_at,
            updated_at=record.observed_at,
        )

    def with_merged_snapshot(self, record: RawProductRecord) -> Product:
        """Builds the candidate merged `Product` after folding in `record`
        (which may be a re-sync of an already-known source or a brand new
        source) — used internally by `Product.merge`, not called directly
        by application code."""
        new_snapshots = dict(self.source_snapshots)
        new_snapshots[record.source] = record
        # "Most-recently-updated source's value wins on the live Product"
        # (Addendum 1, §9.3(b)) — a single global winner (by observed_at)
        # supplies any field it has; other sources fill in only fields the
        # winner lacks. Allergen/dietary tags are always a union across
        # every known source (never silently drop a safety-relevant tag).
        winner = max(new_snapshots.values(), key=lambda r: r.observed_at)
        others = [r for r in new_snapshots.values() if r is not winner]

        def _pick(field: str) -> Any:
            value = getattr(winner, field)
            if value is not None:
                return value
            for other in others:
                candidate = getattr(other, field)
                if candidate is not None:
                    return candidate
            return None

        barcode = self.barcode or record.barcode
        return Product(
            product_id=self.product_id,
            barcode=barcode,
            name=_pick("name"),
            brand=_pick("brand"),
            category=_pick("category"),
            nutrient_panel=_pick("nutrient_panel"),
            dietary_tags=DietaryTags.union(*(r.dietary_tags for r in new_snapshots.values())),
            allergen_tags=AllergenTags.union(*(r.allergen_tags for r in new_snapshots.values())),
            package_size=_pick("package_size"),
            price=_pick("price"),
            sources=frozenset(new_snapshots.keys()),
            source_snapshots=new_snapshots,
            catalogued_at=self.catalogued_at,
            updated_at=record.observed_at,
        )

    def diff(self, other: Product) -> tuple[str, ...]:
        changed = []
        for field in _COMPARABLE_FIELDS:
            if getattr(self, field) != getattr(other, field):
                changed.append(field)
        return tuple(changed)

    @classmethod
    def merge(cls, existing: Product | None, incoming: RawProductRecord) -> MergeResult:
        if existing is None:
            product = cls.from_first_record(uuid.uuid4(), incoming)
            return MergeResult(product=product, changed_fields=(), is_new=True)

        candidate = existing.with_merged_snapshot(incoming)
        changed_fields = existing.diff(candidate)
        sources_changed = candidate.sources != existing.sources
        if not changed_fields and not sources_changed:
            # Genuinely identical re-sync of an already-known source — no
            # persistence-worthy change at all, not even a new source
            # gained. Return `existing` as-is (cheap short-circuit).
            return MergeResult(product=existing, changed_fields=(), is_new=False)
        # A newly-seen source that simply corroborates the existing data
        # (no field-level conflict) still needs to be persisted (the
        # `sources` set grew, and its raw snapshot must be retained in
        # `product_sources`) — but does not warrant a `ProductUpdated`
        # event, since nothing the read side/consumers observe actually
        # changed (implementation plan section 5: an event with empty
        # `changed_fields` must never be published).
        return MergeResult(product=candidate, changed_fields=changed_fields, is_new=False)


@dataclass(frozen=True, slots=True)
class MergeResult:
    product: Product
    changed_fields: tuple[str, ...]
    is_new: bool
