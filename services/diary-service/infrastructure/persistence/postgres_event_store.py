"""PostgresEventStore -- implements EventStorePort. Single adapter shared
by all 4 aggregate types (implementation plan section 3/9.5), backed by
the one `diary_events` table, discriminated by `aggregate_type`.

append() participates in the caller's existing AsyncSession/transaction so
an event append, its outbox row, commit atomically (outbox pattern,
messaging-conventions SKILL.md). It assigns `aggregate_sequence =
expected_version` and relies on the unique index on
(aggregate_type, aggregate_id, aggregate_sequence) to serialize concurrent
writers racing for the same stream position -- the loser's flush raises an
IntegrityError, translated here to OptimisticConcurrencyError (test-plan
section 2's concurrent-append case).

load() returns events in append order (by the monotonic `sequence` column,
not `occurred_at`, which is not guaranteed strictly increasing under
concurrent writers) -- an unknown aggregate_id returns an empty list, not
an error, so each aggregate's "not found" case is the caller's
responsibility to detect (empty list).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from domain.events.base import DomainEvent, EventMetadata
from domain.ports.event_store_port import OptimisticConcurrencyError
from infrastructure.persistence.models import DiaryEventModel


def event_row_to_domain_event(row: DiaryEventModel) -> DomainEvent:
    return DomainEvent(
        event_id=row.event_id,
        event_type=row.event_type,
        version=row.version,
        aggregate_id=row.aggregate_id,
        payload=row.payload,
        metadata=EventMetadata(**row.event_metadata),
        occurred_at=row.occurred_at,
    )


class PostgresEventStore:
    """Implements domain.ports.event_store_port.EventStorePort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, aggregate_type: str, event: DomainEvent, expected_version: int) -> None:
        row = DiaryEventModel(
            event_id=event.event_id,
            aggregate_type=aggregate_type,
            aggregate_id=event.aggregate_id,
            aggregate_sequence=expected_version,
            event_type=event.event_type,
            version=event.version,
            payload=event.payload,
            event_metadata={
                "correlation_id": event.metadata.correlation_id,
                "causation_id": event.metadata.causation_id,
                "user_id": event.metadata.user_id,
            },
            occurred_at=event.occurred_at,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise OptimisticConcurrencyError(
                f"Concurrent append lost the race for {aggregate_type}/{event.aggregate_id} "
                f"at position {expected_version}."
            ) from exc

    async def load(self, aggregate_type: str, aggregate_id: str) -> list[DomainEvent]:
        stmt = (
            select(DiaryEventModel)
            .where(
                DiaryEventModel.aggregate_type == aggregate_type,
                DiaryEventModel.aggregate_id == aggregate_id,
            )
            .order_by(DiaryEventModel.sequence.asc())
        )
        result = await self._session.execute(stmt)
        return [event_row_to_domain_event(row) for row in result.scalars()]
