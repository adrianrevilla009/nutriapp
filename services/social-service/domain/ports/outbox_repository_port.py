"""The port `PostgresOutboxRepository` implements and `OutboxRelayWorker`
consumes -- social-service's own slice of the repo-wide Outbox Pattern
(messaging-conventions SKILL.md), backing the `UserFollowed`/
`UserUnfollowed` events this service publishes."""

from __future__ import annotations

import uuid
from typing import Protocol

from domain.events.base import DomainEvent


class OutboxRepositoryPort(Protocol):
    """Write path (`enqueue`) runs in the same DB transaction as the
    triggering follow/unfollow write; the relay worker only ever calls
    `fetch_unpublished`/`mark_published`, never `enqueue`."""

    async def enqueue(self, event: DomainEvent) -> None: ...

    async def fetch_unpublished(self, limit: int = 100) -> list[DomainEvent]: ...

    async def mark_published(self, event_id: uuid.UUID) -> None: ...
