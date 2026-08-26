"""PostgresSearchReadModel — implements SearchReadPort.

Full-text (tsvector/GIN) + typo-tolerant (pg_trgm) search per ADR-0012,
combined with dietary/allergen array filters. Dietary tags use Postgres'
array-contains operator (`@>`) so every requested tag must be present
(AND semantics, never OR); allergen exclusion uses array-overlap (`&&`)
negated so a product carrying *any* excluded allergen is dropped.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.ports.search_read_port import ProductSearchPage, ProductSearchQuery
from infrastructure.persistence.mappers import model_to_product_without_sources
from infrastructure.persistence.models import ProductModel


class PostgresSearchReadModel:
    """Implements domain.ports.search_read_port.SearchReadPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search(self, query: ProductSearchQuery) -> ProductSearchPage:
        conditions = []

        if query.dietary_tags:
            wanted = [t.value for t in query.dietary_tags]
            conditions.append(ProductModel.dietary_tags.op("@>")(wanted))

        if query.allergen_tags_excluded:
            excluded = [t.value for t in query.allergen_tags_excluded]
            conditions.append(~ProductModel.allergen_tags.op("&&")(excluded))

        base_stmt = select(ProductModel)
        count_stmt = select(func.count()).select_from(ProductModel)
        for condition in conditions:
            base_stmt = base_stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        if query.text:
            ts_query = func.plainto_tsquery("simple", query.text)
            similarity = func.similarity(func.coalesce(ProductModel.name, ""), query.text)
            text_condition = ProductModel.search_vector.op("@@")(ts_query) | (similarity > 0.3)
            base_stmt = base_stmt.where(text_condition)
            count_stmt = count_stmt.where(text_condition)
            rank = func.ts_rank(ProductModel.search_vector, ts_query) + similarity
            base_stmt = base_stmt.order_by(rank.desc())
        else:
            base_stmt = base_stmt.order_by(ProductModel.updated_at.desc())

        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        offset = (query.page - 1) * query.page_size
        base_stmt = base_stmt.offset(offset).limit(query.page_size)
        result = await self._session.execute(base_stmt)
        items = tuple(model_to_product_without_sources(row) for row in result.scalars())

        return ProductSearchPage(
            items=items, total=total, page=query.page, page_size=query.page_size
        )
