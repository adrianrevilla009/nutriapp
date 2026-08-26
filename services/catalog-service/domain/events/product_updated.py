"""ProductUpdated (v1) — see docs/events-catalog.md.

Same payload shape as `ProductCatalogued` plus `changed_fields`, emitted
when an already-catalogued product's data changes on a subsequent
ingestion pass. An event with an empty `changed_fields` list must never be
published (that is a no-op merge, test-plan section 3) — enforced by the
caller (application/commands/ingest_product_batch.py), not this module.
"""

from __future__ import annotations

from domain.entities.product import Product
from domain.events.base import DomainEvent, EventMetadata
from domain.events.product_catalogued import build_product_payload

EVENT_TYPE = "ProductUpdated"
EVENT_VERSION = 1


def build_product_updated_event(
    *, product: Product, changed_fields: tuple[str, ...], correlation_id: str
) -> DomainEvent:
    if not changed_fields:
        raise ValueError(
            "ProductUpdated must never be published with an empty changed_fields list."
        )
    payload = build_product_payload(product)
    payload["changed_fields"] = list(changed_fields)
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(product.product_id),
        payload=payload,
        metadata=EventMetadata(correlation_id=correlation_id),
    )
