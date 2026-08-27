import time
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.entities.product import Product
from domain.ports.search_read_port import ProductSearchQuery
from domain.value_objects.allergen_tags import AllergenTag, AllergenTags
from domain.value_objects.barcode import Barcode
from domain.value_objects.dietary_tags import DietaryTag, DietaryTags
from infrastructure.persistence.postgres_product_repository import PostgresProductRepository
from infrastructure.persistence.postgres_search_read_model import PostgresSearchReadModel
from tests.fixtures.factories import make_raw_record

pytestmark = pytest.mark.usefixtures("db_engine")


@pytest.fixture
async def session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s


async def _seed(session, **overrides) -> Product:
    repo = PostgresProductRepository(session)
    record = make_raw_record(**overrides)
    product = Product.merge(existing=None, incoming=record).product
    await repo.save(product)
    await session.commit()
    return product


async def test_exact_name_match_returns_product(session):
    await _seed(session, name="Organic Almond Milk", barcode=Barcode("5901234123457"))
    read_model = PostgresSearchReadModel(session)

    page = await read_model.search(
        ProductSearchQuery(
            text="Almond Milk", dietary_tags=frozenset(), allergen_tags_excluded=frozenset()
        )
    )

    assert page.total == 1
    assert page.items[0].name == "Organic Almond Milk"


async def test_typo_tolerant_partial_match_returns_product(session):
    await _seed(session, name="Chocolate Digestive Biscuits", barcode=Barcode("036000291452"))
    read_model = PostgresSearchReadModel(session)

    page = await read_model.search(
        ProductSearchQuery(
            text="Chocolat Digestiv", dietary_tags=frozenset(), allergen_tags_excluded=frozenset()
        )
    )

    assert page.total >= 1
    assert any("Digestive" in (p.name or "") for p in page.items)


async def test_dietary_and_text_filters_combine_with_and_not_or(session):
    await _seed(
        session,
        name="Vegan Protein Bar",
        source_product_id="off-1",
        barcode=Barcode("5901234123457"),
        dietary_tags=DietaryTags(frozenset({DietaryTag.VEGAN})),
    )
    await _seed(
        session,
        name="Vegan Protein Shake",
        source_product_id="off-2",
        barcode=Barcode("036000291452"),
        dietary_tags=DietaryTags.empty(),
    )
    read_model = PostgresSearchReadModel(session)

    page = await read_model.search(
        ProductSearchQuery(
            text="Vegan Protein",
            dietary_tags=frozenset({DietaryTag.VEGAN}),
            allergen_tags_excluded=frozenset(),
        )
    )

    assert page.total == 1
    assert page.items[0].name == "Vegan Protein Bar"


async def test_allergen_exclusion_filters_out_matching_products(session):
    await _seed(
        session,
        name="Peanut Butter Cookies",
        source_product_id="off-1",
        barcode=Barcode("5901234123457"),
        allergen_tags=AllergenTags(frozenset({AllergenTag.PEANUTS})),
    )
    read_model = PostgresSearchReadModel(session)

    page = await read_model.search(
        ProductSearchQuery(
            text="Cookies",
            dietary_tags=frozenset(),
            allergen_tags_excluded=frozenset({AllergenTag.PEANUTS}),
        )
    )

    assert page.total == 0


async def test_search_p95_latency_smoke_under_300ms(session):
    repo = PostgresProductRepository(session)
    for i in range(500):
        # No barcode needed for this seed data (bypasses check-digit
        # validation overhead at volume) — the search read model only
        # cares about indexed text columns for this smoke assertion.
        record = make_raw_record(
            barcode=None,
            source_product_id=f"off-seed-{i}",
            name=f"Seed Product {i} Snack Bar",
            observed_at=datetime.now(timezone.utc),
        )
        product = Product.merge(existing=None, incoming=record).product
        await repo.save(product)
    await session.commit()

    read_model = PostgresSearchReadModel(session)
    start = time.perf_counter()
    page = await read_model.search(
        ProductSearchQuery(
            text="Snack Bar", dietary_tags=frozenset(), allergen_tags_excluded=frozenset()
        )
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert page.total > 0
    assert elapsed_ms < 300
