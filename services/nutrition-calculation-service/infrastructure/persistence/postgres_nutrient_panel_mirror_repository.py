"""PostgresNutrientPanelMirrorRepository -- implements
NutrientPanelMirrorPort. Upsert on `ProductCatalogued`/`ProductUpdated`
(a mirror, never an append -- test-plan section 2)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.models import NutrientPanelMirrorModel


class PostgresNutrientPanelMirrorRepository:
    """Implements domain.ports.nutrient_panel_mirror_port.NutrientPanelMirrorPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_reference_id(
        self, source_reference_id: str
    ) -> Mapping[str, float | None] | None:
        row = await self._session.get(NutrientPanelMirrorModel, source_reference_id)
        return dict(row.panel) if row is not None else None

    async def upsert(self, source_reference_id: str, panel: Mapping[str, float | None]) -> None:
        row = await self._session.get(NutrientPanelMirrorModel, source_reference_id)
        if row is None:
            row = NutrientPanelMirrorModel(source_reference_id=source_reference_id)
            self._session.add(row)
        row.panel = dict(panel)
        row.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
