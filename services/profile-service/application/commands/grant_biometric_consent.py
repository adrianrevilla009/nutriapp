"""GrantBiometricConsentCommand + handler -- CLAUDE.md section 8: explicit,
specific consent, required before any metric can be recorded."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from application.errors import ProfileNotFoundError
from domain.entities.profile import Profile
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.ports.profile_event_store_port import ProfileEventStorePort
from domain.ports.snapshot_projector_port import SnapshotProjectorPort


@dataclass(frozen=True, slots=True)
class GrantBiometricConsentCommand:
    user_id: uuid.UUID
    correlation_id: str


@dataclass(frozen=True, slots=True)
class GrantBiometricConsentResult:
    consent_granted: bool


class GrantBiometricConsentHandler:
    def __init__(
        self,
        event_store: ProfileEventStorePort,
        outbox: OutboxRepositoryPort,
        snapshot_projector: SnapshotProjectorPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._event_store = event_store
        self._outbox = outbox
        self._snapshot_projector = snapshot_projector
        self._now_fn = now_fn

    async def handle(self, command: GrantBiometricConsentCommand) -> GrantBiometricConsentResult:
        events = await self._event_store.load(command.user_id)
        if not events:
            raise ProfileNotFoundError("No profile exists yet for this user_id.")
        profile = Profile.rebuild(events)

        if profile.consent_granted:
            return GrantBiometricConsentResult(consent_granted=True)

        event = profile.grant_consent(
            granted_at=self._now_fn(), correlation_id=command.correlation_id
        )
        await self._event_store.append(event)
        await self._outbox.enqueue(event)
        await self._snapshot_projector.apply(event)
        return GrantBiometricConsentResult(consent_granted=True)
