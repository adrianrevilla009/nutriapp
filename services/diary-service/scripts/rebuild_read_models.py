"""Operational rebuild path for diary-service's disposable read models
(`food_entries_view`, `water_intake_view`, `fasting_windows_view`,
`meal_plan_view`, `daily_summary_view`) -- makes the CQRS invariant that a
read model must always be rebuildable by replaying the event store
(cqrs-event-sourcing SKILL.md) an actual, runnable capability, not just an
assertion in docstrings.

Truncates all 5 read-model tables, then replays every row in
`diary_events`, grouped by (aggregate_type, aggregate_id) and ordered
chronologically WITHIN each group (by the monotonic `sequence` column --
never `occurred_at`, which is not guaranteed strictly increasing under
concurrent writers, per postgres_event_store.py), through the exact same
`apply_event_to_read_models()` helper the live async consumer uses. This
produces the same read-model state the async projectors would have
produced from a from-empty replay of writes.

Usage (README.md "Read-model rebuild" runbook step):
    cd services/diary-service
    DIARY_SERVICE_DATABASE_URL=postgresql+asyncpg://... \
        python -m scripts.rebuild_read_models

Never run against a database with concurrent writers without first pausing
the write path (or accept that events appended after this script reads
`diary_events` will simply be missing until the next normal write
re-projects them via the live async consumer).
"""

from __future__ import annotations

import asyncio
import itertools
import os

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from infrastructure.messaging.diary_event_projector_consumer import (
    apply_event_to_read_models,
)
from infrastructure.persistence.models import (
    DailySummaryViewModel,
    DiaryEventModel,
    FastingWindowViewModel,
    FoodEntryViewModel,
    MealPlanViewModel,
    WaterIntakeViewModel,
)
from infrastructure.persistence.postgres_event_store import event_row_to_domain_event


async def rebuild_read_models(session: AsyncSession) -> int:
    """Truncates all 5 read-model tables and replays every event in
    `diary_events` ((aggregate_type, aggregate_id)-then-chronological
    order) through the same `apply_event_to_read_models()` helper the live
    consumer uses. Returns the number of events replayed. Caller is
    responsible for the session's lifecycle (this function does not open/
    close the session, only executes statements and commits)."""
    await session.execute(delete(DailySummaryViewModel))
    await session.execute(delete(FoodEntryViewModel))
    await session.execute(delete(WaterIntakeViewModel))
    await session.execute(delete(FastingWindowViewModel))
    await session.execute(delete(MealPlanViewModel))
    await session.flush()

    stmt = select(DiaryEventModel).order_by(
        DiaryEventModel.aggregate_type.asc(),
        DiaryEventModel.aggregate_id.asc(),
        DiaryEventModel.sequence.asc(),
    )
    result = await session.execute(stmt)
    rows = list(result.scalars())

    replayed = 0
    for _key, group_rows in itertools.groupby(
        rows, key=lambda r: (r.aggregate_type, r.aggregate_id)
    ):
        for row in group_rows:
            event = event_row_to_domain_event(row)
            await apply_event_to_read_models(session, event, redis_cache=None)
            replayed += 1

    await session.commit()
    return replayed


async def main() -> None:  # pragma: no cover -- thin CLI wrapper, exercised via rebuild_read_models
    database_url = os.environ["DIARY_SERVICE_DATABASE_URL"]
    engine = create_async_engine(database_url)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            replayed = await rebuild_read_models(session)
            print(f"Rebuilt diary-service read models from {replayed} replayed events.")
    finally:
        await engine.dispose()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
