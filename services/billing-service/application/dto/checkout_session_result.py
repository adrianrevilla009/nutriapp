from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CheckoutSessionResult:
    stripe_session_id: str
    url: str
