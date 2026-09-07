"""EventPublisherPort -- scaffolded for architectural symmetry with every
other event-driven-CRUD service in this repo (ADR-0002 addendum). Unused
this pass: no other service is documented as consuming anything from
nutrition-assistant-service (implementation plan section 5) -- flagged
explicitly rather than silently included as if it had a real caller."""

from __future__ import annotations

from typing import Any, Protocol


class EventPublisherPort(Protocol):
    async def publish(self, event: Any) -> None: ...
