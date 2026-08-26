"""DailySummaryCachePort -- Redis cache-aside for the daily_summary_view
"hot aggregate" (implementation plan section 7, caching-strategy
SKILL.md). Key namespace: diary:{user_id}:summary:{date}. TTL: 60s.
Invalidation is event-driven (the daily_summary_projector invalidates the
affected key immediately after updating Postgres for every event that
touches that user+date), not purely TTL-based.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Protocol

DAILY_SUMMARY_CACHE_TTL_SECONDS = 60


class DailySummaryCachePort(Protocol):
    async def get(self, user_id: uuid.UUID, summary_date: date) -> dict[str, Any] | None: ...

    async def set(
        self, user_id: uuid.UUID, summary_date: date, summary: dict[str, Any]
    ) -> None: ...

    async def invalidate(self, user_id: uuid.UUID, summary_date: date) -> None: ...
