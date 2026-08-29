"""EmailProviderPort -- ADR-0001 port; Amazon SES is the adapter
(ses_email_adapter.py, ADR-0011). Swapping the email provider must never
touch application or domain code."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class EmailProviderUnavailableError(Exception):
    """Raised when the email provider call fails or its circuit is open."""


@dataclass(frozen=True, slots=True)
class EmailSendResult:
    provider_message_id: str


class EmailProviderPort(Protocol):
    async def send(
        self, *, to: str, subject: str, html_body: str, correlation_id: str
    ) -> EmailSendResult: ...
