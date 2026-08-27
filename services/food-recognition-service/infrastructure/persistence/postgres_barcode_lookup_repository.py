"""PostgresBarcodeLookupRepository -- implements
BarcodeLookupRepositoryPort. Append-only writes only."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.barcode_lookup import BarcodeLookup
from infrastructure.persistence.models import BarcodeLookupModel


class PostgresBarcodeLookupRepository:
    """Implements domain.ports.barcode_lookup_repository_port.BarcodeLookupRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, lookup: BarcodeLookup) -> None:
        row = BarcodeLookupModel(
            lookup_id=lookup.lookup_id,
            user_id=lookup.user_id,
            submitted_at=lookup.submitted_at,
            decoded_barcode=lookup.decoded_barcode,
            matched_product_id=lookup.matched_product_id,
            status=lookup.status,
        )
        self._session.add(row)
        await self._session.flush()

    async def get_by_id(self, lookup_id: object) -> BarcodeLookup | None:
        row = await self._session.get(BarcodeLookupModel, lookup_id)
        if row is None:
            return None
        return BarcodeLookup(
            lookup_id=row.lookup_id,
            user_id=row.user_id,
            submitted_at=row.submitted_at,
            decoded_barcode=row.decoded_barcode,
            matched_product_id=row.matched_product_id,
            status=row.status,  # type: ignore[arg-type]
        )
