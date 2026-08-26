"""PostgresIngestionRunRepository — audit trail for each ingestion run
(implementation plan section 3): not behind a domain port (it is a pure
observability/audit concern of the ingestion job orchestration, not
something the domain layer needs to know about), called directly by
whatever schedules `run_open_food_facts_ingestion`/`run_usda_fdc_ingestion`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from application.jobs.run_open_food_facts_ingestion import IngestionRunSummary
from infrastructure.persistence.models import IngestionRunModel


class PostgresIngestionRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def start(self, source: str) -> uuid.UUID:
        run_id = uuid.uuid4()
        row = IngestionRunModel(
            run_id=run_id,
            source=source,
            started_at=datetime.now(timezone.utc),
            finished_at=None,
            status="running",
        )
        self._session.add(row)
        await self._session.flush()
        return run_id

    async def finish(self, run_id: uuid.UUID, summary: IngestionRunSummary) -> None:
        row = await self._session.get(IngestionRunModel, run_id)
        if row is None:
            return
        row.finished_at = datetime.now(timezone.utc)
        row.items_seen = summary.items_seen
        row.items_added = summary.items_added
        row.items_updated = summary.items_updated
        row.items_skipped = summary.items_skipped
        row.status = summary.status
        await self._session.flush()
