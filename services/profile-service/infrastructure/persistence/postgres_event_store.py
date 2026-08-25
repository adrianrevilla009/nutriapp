"""PostgresEventStore -- implements ProfileEventStorePort.

append() participates in the caller's existing AsyncSession/transaction
(same pattern as identity-service's PostgresOutboxRepository) so an event
append, its outbox row, and its projection writes all commit atomically.
load() returns events in append order (by the monotonic `sequence`
column, not `occurred_at`, which is not guaranteed strictly increasing
under concurrent writers) -- an unknown aggregate_id returns an empty
list, not an error, so Profile.rebuild()'s "no profile yet" case is the
caller's responsibility to detect (empty list), per test-plan section 2.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.events.base import DomainEvent, EventMetadata
from infrastructure.persistence.models import ProfileEventModel


def event_row_to_domain_event(row: ProfileEventModel) -> DomainEvent:
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
    """Implements domain.ports.profile_event_store_port.ProfileEventStorePort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, event: DomainEvent) -> None:
        row = ProfileEventModel(
            event_id=event.event_id,
            aggregate_id=event.aggregate_id,
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
        await self._session.flush()

    async def load(self, user_id: uuid.UUID) -> list[DomainEvent]:
        stmt = (
            select(ProfileEventModel)
            .where(ProfileEventModel.aggregate_id == str(user_id))
            .order_by(ProfileEventModel.sequence.asc())
        )
        result = await self._session.execute(stmt)
        return [event_row_to_domain_event(row) for row in result.scalars()]
