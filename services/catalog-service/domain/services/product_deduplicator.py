"""product_deduplicator — resolves the dedup/merge key for a
`RawProductRecord`, per Addendum 1 §9.3(a): barcode is the sole
cross-source dedup key; no fuzzy name+brand matching (too high a
false-merge risk for data feeding nutrition calculations downstream).

Records with no barcode are never merged across sources — their identity
is scoped to `(source, source_product_id)` instead, so a re-sync from the
same source updates the same product, but two different sources'
barcode-less records are always treated as distinct products.
"""

from __future__ import annotations

from collections import defaultdict

from domain.services.product_normalizer import RawProductRecord

DedupKey = str


def resolve_dedup_key(record: RawProductRecord) -> DedupKey:
    if record.barcode is not None:
        return f"barcode:{record.barcode}"
    return f"source:{record.source.value}:{record.source_product_id}"


def same_dedup_key(a: RawProductRecord, b: RawProductRecord) -> bool:
    return resolve_dedup_key(a) == resolve_dedup_key(b)


def group_by_dedup_key(
    records: list[RawProductRecord],
) -> dict[DedupKey, list[RawProductRecord]]:
    grouped: dict[DedupKey, list[RawProductRecord]] = defaultdict(list)
    for record in records:
        grouped[resolve_dedup_key(record)].append(record)
    return dict(grouped)
