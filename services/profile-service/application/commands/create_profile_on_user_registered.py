"""Reactive profile creation on identity-service's UserRegistered (v1).

Idempotent by event_id (messaging-conventions SKILL.md) -- this handler is
invoked by infrastructure/messaging/user_registered_consumer.py, once per
delivery, which may redeliver at-least-once.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from domain.entities.profile import Profile
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.ports.processed_events_port import ProcessedEventsPort
from domain.ports.profile_event_store_port import ProfileEventStorePort


@dataclass(frozen=True, slots=True)
class CreateProfileOnUserRegisteredCommand:
    user_id: uuid.UUID
    source_event_id: uuid.UUID
    correlation_id: str


@dataclass(frozen=True, slots=True)
class CreateProfileOnUserRegisteredResult:
    created: bool


class CreateProfileOnUserRegisteredHandler:
    def __init__(
        self,
        event_store: ProfileEventStorePort,
        outbox: OutboxRepositoryPort,
        processed_events: ProcessedEventsPort,
    ) -> None:
        self._event_store = event_store
        self._outbox = outbox
        self._processed_events = processed_events

    async def handle(
        self, command: CreateProfileOnUserRegisteredCommand
    ) -> CreateProfileOnUserRegisteredResult:
        if await self._processed_events.already_processed(command.source_event_id):
            return CreateProfileOnUserRegisteredResult(created=False)

        _profile, event = Profile.create(
            user_id=command.user_id,
            correlation_id=command.correlation_id,
            causation_id=str(command.source_event_id),
        )
        await self._event_store.append(event)
        await self._outbox.enqueue(event)
        await self._processed_events.mark_processed(command.source_event_id)
        return CreateProfileOnUserRegisteredResult(created=True)
