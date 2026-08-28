"""GET /internal/v1/catalog/lookup — implementation plan Addendum 2.

Mirrors identity-service's reveal-endpoint credential test: a
missing/wrong `X-Internal-Service-Credential` header is rejected before
the product repository is even built (before touching the DB) — see
`infrastructure/http/routes/internal_catalog_routes.py`.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.product import Product
from infrastructure.persistence.postgres_product_repository import PostgresProductRepository
from tests.contract.http.conftest import INTERNAL_LOOKUP_CREDENTIAL
from tests.fixtures.factories import make_raw_record

pytestmark = pytest.mark.usefixtures("db_engine")

KNOWN_BARCODE = "5901234123457"


async def test_lookup_missing_credential_returns_401_without_hitting_db(app_client):
    response = await app_client.get(
        "/internal/v1/catalog/lookup", params={"barcode": KNOWN_BARCODE}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CALLER_CREDENTIAL"


async def test_lookup_wrong_credential_returns_401_without_hitting_db(app_client):
    response = await app_client.get(
        "/internal/v1/catalog/lookup",
        params={"barcode": KNOWN_BARCODE},
        headers={"X-Internal-Service-Credential": "wrong-credential"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CALLER_CREDENTIAL"


async def test_lookup_valid_credential_known_barcode_returns_200_matching_product_shape(
    app_client, db_engine
):
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresProductRepository(session)
        record = make_raw_record()
        product = Product.merge(existing=None, incoming=record).product
        await repo.save(product)
        await session.commit()

    lookup_response = await app_client.get(
        "/internal/v1/catalog/lookup",
        params={"barcode": str(product.barcode)},
        headers={"X-Internal-Service-Credential": INTERNAL_LOOKUP_CREDENTIAL},
    )
    by_id_response = await app_client.get(f"/api/v1/catalog/products/{product.product_id}")

    assert lookup_response.status_code == 200
    assert lookup_response.json() == by_id_response.json()


async def test_lookup_valid_credential_unknown_barcode_returns_404(app_client):
    response = await app_client.get(
        "/internal/v1/catalog/lookup",
        params={"barcode": KNOWN_BARCODE},
        headers={"X-Internal-Service-Credential": INTERNAL_LOOKUP_CREDENTIAL},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "PRODUCT_NOT_FOUND"


async def test_lookup_route_is_not_registered_under_api_v1_prefix(app_client):
    # Asserts the internal endpoint is absent from the public API surface
    # (never routed through Kong) -- Kong only forwards /api/v1/* paths.
    response = await app_client.get("/openapi.json")
    paths = response.json()["paths"]
    assert all(not p.startswith("/api/v1/internal") for p in paths)
    assert any(p.startswith("/internal/") for p in paths)
