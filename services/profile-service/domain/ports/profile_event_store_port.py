from __future__ import annotations

import uuid
from typing import Protocol

from domain.events.base import DomainEvent


class ProfileEventStorePort(Protocol):
    async def append(self, event: DomainEvent) -> None: ...

    async def load(self, user_id: uuid.UUID) -> list[DomainEvent]: ...
