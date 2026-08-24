"""Device fingerprint value object.

Simple heuristic per the implementation plan §9.4: hash(User-Agent + IP).
Not a strong anti-fraud signal — good enough for a "new device" nudge
email, nothing more.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeviceFingerprint:
    """A stable hash identifying a (User-Agent, IP) pair."""

    hash_value: str

    @classmethod
    def from_request_context(cls, user_agent: str, ip_address: str) -> DeviceFingerprint:
        raw = f"{user_agent}|{ip_address}".encode()
        digest = hashlib.sha256(raw).hexdigest()
        return cls(hash_value=digest)

    def __str__(self) -> str:
        return self.hash_value
