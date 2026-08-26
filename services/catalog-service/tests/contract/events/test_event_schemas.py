"""ProductCatalogued/ProductUpdated published payloads match
packages/shared-contracts/schemas/*.json (test-plan section 3)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import jsonschema

from domain.entities.product import Product
from domain.events.product_catalogued import build_product_catalogued_event
from domain.events.product_updated import build_product_updated_event
from tests.fixtures.factories import make_raw_record

SCHEMAS_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "..",
    "..",
    "packages",
    "shared-contracts",
    "schemas",
)


def _load_schema(name: str) -> dict:
    with open(os.path.join(SCHEMAS_DIR, name)) as f:
        return json.load(f)


def test_product_catalogued_payload_matches_schema():
    schema = _load_schema("product_catalogued.v1.json")
    product = Product.merge(existing=None, incoming=make_raw_record()).product
    event = build_product_catalogued_event(product=product, correlation_id="c1")

    jsonschema.validate(instance=event.to_wire(), schema=schema)


def test_product_updated_payload_matches_schema_with_nonempty_changed_fields():
    schema = _load_schema("product_updated.v1.json")
    product = Product.merge(existing=None, incoming=make_raw_record()).product
    updated_record = make_raw_record(name="New Name", observed_at=datetime.now(timezone.utc))
    result = Product.merge(existing=product, incoming=updated_record)

    event = build_product_updated_event(
        product=result.product, changed_fields=result.changed_fields, correlation_id="c2"
    )

    jsonschema.validate(instance=event.to_wire(), schema=schema)
    assert len(event.payload["changed_fields"]) >= 1


def test_product_updated_never_published_with_empty_changed_fields():
    product = Product.merge(existing=None, incoming=make_raw_record()).product
    import pytest

    with pytest.raises(ValueError):
        build_product_updated_event(product=product, changed_fields=(), correlation_id="c3")
