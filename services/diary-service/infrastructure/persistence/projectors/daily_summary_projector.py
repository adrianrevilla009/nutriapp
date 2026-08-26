"""PostgresDailySummaryProjector -- writes AND reads daily_summary_view,
the "hot aggregate" cached in Redis (implementation plan section 7).

Rather than incrementally diffing deltas (which would require tracking a
prior contribution per source event -- awkward for FoodEntryCorrected,
which replaces a prior contribution with a new one), this projector
recomputes the affected user+date bucket declaratively by re-aggregating
the already-updated food_entries_view / water_intake_view /
fasting_windows_view rows. This requires those three projectors to have
already applied the same event before this one runs -- the dispatch order
enforced by infrastructure/messaging/diary_event_projector_consumer.py and
scripts/rebuild_read_models.py (entity-specific projector first, then
this one).

Known, documented limitation: correcting a FoodEntryLogged's occurred_at
to a DIFFERENT calendar date only recomputes the new date's bucket, not
the original date's (which goes stale until another event touches it).
Not exercised by any acceptance criterion in this plan; flagged here
rather than silently accepted.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from domain.events.base import DomainEvent
from infrastructure.persistence.models import DailySummaryViewModel
from infrastructure.persistence.projectors.fasting_windows_projector import (
    PostgresFastingWindowsProjector,
)
from infrastructure.persistence.projectors.food_entries_projector import (
    PostgresFoodEntriesProjector,
)
from infrastructure.persistence.projectors.water_intake_projector import (
    PostgresWaterIntakeProjector,
)

_FOOD_EVENT_TYPES = frozenset({"FoodEntryLogged", "FoodEntryCorrected", "FoodEntryDeleted"})
_WATER_EVENT_TYPES = frozenset({"WaterIntakeLogged", "WaterIntakeRemoved"})


class PostgresDailySummaryProjector:
    """Implements DailySummaryReadPort and the write side used by
    diary_event_projector_consumer / scripts/rebuild_read_models.py."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._food_projector = PostgresFoodEntriesProjector(session)
        self._water_projector = PostgresWaterIntakeProjector(session)
        self._fasting_projector = PostgresFastingWindowsProjector(session)

    async def apply(self, event: DomainEvent) -> tuple[uuid.UUID, date] | None:
        """Recomputes the affected user+date bucket. Returns the
        (user_id, date) pair touched, or None if this event type doesn't
        affect the daily summary -- the caller (the async consumer) uses
        this to invalidate exactly that Redis cache key."""
        user_id = uuid.UUID(event.payload["user_id"])

        if event.event_type in _FOOD_EVENT_TYPES or event.event_type in _WATER_EVENT_TYPES:
            summary_date = datetime.fromisoformat(event.payload["occurred_at"]).date()
        elif event.event_type == "FastingWindowEnded":
            summary_date = datetime.fromisoformat(event.payload["ended_at"]).date()
        else:
            return None

        food_totals = await self._food_projector.get_daily_totals(user_id, summary_date)
        water_total_ml = await self._water_projector.get_daily_total_ml(user_id, summary_date)
        fasting_count = await self._fasting_projector.count_ended_on(user_id, summary_date)

        stmt = (
            pg_insert(DailySummaryViewModel)
            .values(
                user_id=user_id,
                summary_date=summary_date.isoformat(),
                total_calories_kcal=food_totals["total_calories_kcal"],
                total_protein_g=food_totals["total_protein_g"],
                total_carbs_g=food_totals["total_carbs_g"],
                total_fat_g=food_totals["total_fat_g"],
                total_water_ml=water_total_ml,
                fasting_windows_ended=fasting_count,
                updated_at=event.occurred_at,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "summary_date"],
                set_={
                    "total_calories_kcal": food_totals["total_calories_kcal"],
                    "total_protein_g": food_totals["total_protein_g"],
                    "total_carbs_g": food_totals["total_carbs_g"],
                    "total_fat_g": food_totals["total_fat_g"],
                    "total_water_ml": water_total_ml,
                    "fasting_windows_ended": fasting_count,
                    "updated_at": event.occurred_at,
                },
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()
        return user_id, summary_date

    async def get_summary(self, user_id: uuid.UUID, summary_date: date) -> dict[str, Any] | None:
        row = await self._session.get(DailySummaryViewModel, (user_id, summary_date.isoformat()))
        if row is None:
            return None
        return {
            "total_calories_kcal": row.total_calories_kcal,
            "total_protein_g": row.total_protein_g,
            "total_carbs_g": row.total_carbs_g,
            "total_fat_g": row.total_fat_g,
            "total_water_ml": row.total_water_ml,
            "fasting_windows_ended": row.fasting_windows_ended,
        }
