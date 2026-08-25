"""Operational rebuild path for profile-service's disposable read models
(`profile_snapshot`, `profile_evolution`) -- makes the CQRS invariant that
a read model must always be rebuildable by replaying the event store
(cqrs-event-sourcing SKILL.md) an actual, runnable capability, not just an
assertion in docstrings.

Truncates both read-model tables, then replays every row in
`profile_events`, grouped by aggregate (`user_id`/`aggregate_id`) and
ordered chronologically *within* each aggregate (by the monotonic
`sequence` column -- never `occurred_at`, which is not guaranteed strictly
increasing under concurrent writers, per postgres_event_store.py), through
the exact same `apply()` methods the command handlers already call
synchronously on every write. This produces byte-for-byte the same rows a
from-empty replay of writes would have produced.

Events are replayed exactly as stored (already encrypted-at-rest) -- no
decryption step here, mirroring how command handlers already pass the
encrypted event copy to both projectors immediately after appending it
(application/commands/*.py). `PostgresEvolutionProjector.apply()` is
idempotent under replay (`ON CONFLICT (source_event_id) DO NOTHING`), so
running this script twice without an intervening write is safe, though
truncating first (as this script does) is the documented, expected path.

Usage (README.md "Read-model rebuild" runbook step):
    cd services/profile-service
    PROFILE_SERVICE_DATABASE_URL=postgresql+asyncpg://... \
        python -m scripts.rebuild_read_models

Never run against a database with concurrent writers without first pausing
the write path (or accept that events appended after this script reads
`profile_events` will simply be missing until the next normal write
re-projects them, since normal writes keep applying synchronously).
"""

from __future__ import annotations

import asyncio
import itertools
import os

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from infrastructure.persistence.models import (
    ProfileEventModel,
    ProfileEvolutionModel,
    ProfileSnapshotModel,
)
from infrastructure.persistence.postgres_event_store import event_row_to_domain_event
from infrastructure.persistence.postgres_evolution_projector import PostgresEvolutionProjector
from infrastructure.persistence.postgres_snapshot_projector import PostgresSnapshotProjector


async def rebuild_read_models(session: AsyncSession) -> int:
    """Truncates `profile_snapshot`/`profile_evolution` and replays every
    event in `profile_events` (aggregate-then-chronological order) through
    the same projector `apply()` methods used by command handlers. Returns
    the number of events replayed. Caller is responsible for the session's
    lifecycle (this function does not open/close the session, only
    executes statements and commits)."""
    await session.execute(delete(ProfileEvolutionModel))
    await session.execute(delete(ProfileSnapshotModel))
    await session.flush()

    stmt = select(ProfileEventModel).order_by(
        ProfileEventModel.aggregate_id.asc(), ProfileEventModel.sequence.asc()
    )
    result = await session.execute(stmt)
    rows = list(result.scalars())

    snapshot_projector = PostgresSnapshotProjector(session)
    evolution_projector = PostgresEvolutionProjector(session)

    replayed = 0
    for _aggregate_id, aggregate_rows in itertools.groupby(rows, key=lambda r: r.aggregate_id):
        for row in aggregate_rows:
            event = event_row_to_domain_event(row)
            await snapshot_projector.apply(event)
            await evolution_projector.apply(event)
            replayed += 1

    await session.commit()
    return replayed


async def main() -> None:  # pragma: no cover -- thin CLI wrapper, exercised via rebuild_read_models
    database_url = os.environ["PROFILE_SERVICE_DATABASE_URL"]
    engine = create_async_engine(database_url)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            replayed = await rebuild_read_models(session)
            print(
                f"Rebuilt profile_snapshot and profile_evolution from {replayed} replayed events."
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
