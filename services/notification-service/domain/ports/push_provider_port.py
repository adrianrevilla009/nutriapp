"""PushProviderPort -- ADR-0001 port; Amazon SNS (or FCM/APNs directly,
per ADR-0011) is the adapter (sns_push_adapter.py)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


class PushProviderUnavailableError(Exception):
    """Raised when the push provider call fails or its circuit is open."""


@dataclass(frozen=True, slots=True)
class PushSendResult:
    provider_message_id: str


class PushProviderPort(Protocol):
    async def send(
        self,
        *,
        device_token: str,
        title: str,
        body: str,
        data: Mapping[str, str],
        correlation_id: str,
    ) -> PushSendResult: ...
