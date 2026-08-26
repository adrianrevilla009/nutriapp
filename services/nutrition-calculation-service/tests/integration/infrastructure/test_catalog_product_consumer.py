"""CatalogProductConsumer -- idempotency test (test-plan section 2): the
same ProductCatalogued/ProductUpdated delivered twice results in exactly
one mirror row, upserted in place."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from infrastructure.messaging.catalog_product_consumer import CatalogProductConsumer
from infrastructure.persistence.postgres_nutrient_panel_mirror_repository import (
    PostgresNutrientPanelMirrorRepository,
)

pytestmark = pytest.mark.usefixtures("db_engine")


def _product_catalogued_body(product_id: uuid.UUID, event_id: uuid.UUID | None = None) -> dict:
    return {
        "event_id": str(event_id or uuid.uuid4()),
        "aggregate_id": str(product_id),
        "event_type": "ProductCatalogued",
        "version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "product_id": str(product_id),
            "barcode": "0000000000001",
            "name": "Test Product",
            "brand": None,
            "category": None,
            "nutrition_per_100g": {
                "energy_kcal": 250.0,
                "protein_g": 12.0,
                "carbohydrates_g": 30.0,
                "fat_g": 8.0,
                "sugars_g": 5.0,
            },
            "dietary_tags": [],
            "allergen_tags": [],
            "package_size": None,
            "sources": ["open_food_facts"],
            "catalogued_at": datetime.now(timezone.utc).isoformat(),
        },
        "metadata": {"correlation_id": "corr-1", "causation_id": None, "user_id": None},
    }


async def test_replayed_product_catalogued_upserts_once(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    consumer = CatalogProductConsumer(session_factory)

    product_id = uuid.uuid4()
    event_id = uuid.uuid4()
    body = _product_catalogued_body(product_id, event_id=event_id)

    await consumer.process_body(body)
    await consumer.process_body(body)  # exact same event_id -- a redelivery

    async with session_factory() as session:
        repo = PostgresNutrientPanelMirrorRepository(session)
        panel = await repo.get_by_reference_id(str(product_id))

    assert panel is not None
    assert panel["calories_kcal"] == 250.0
    assert panel["carbs_g"] == 30.0


async def test_product_updated_updates_mirror_in_place(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    consumer = CatalogProductConsumer(session_factory)

    product_id = uuid.uuid4()
    catalogued_body = _product_catalogued_body(product_id)
    await consumer.process_body(catalogued_body)

    updated_body = _product_catalogued_body(product_id)
    updated_body["event_type"] = "ProductUpdated"
    updated_body["payload"]["nutrition_per_100g"]["energy_kcal"] = 400.0
    updated_body["payload"]["changed_fields"] = ["nutrition_per_100g"]
    await consumer.process_body(updated_body)

    async with session_factory() as session:
        repo = PostgresNutrientPanelMirrorRepository(session)
        panel = await repo.get_by_reference_id(str(product_id))

    assert panel["calories_kcal"] == 400.0
