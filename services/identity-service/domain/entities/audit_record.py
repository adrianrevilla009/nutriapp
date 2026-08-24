"""Immutable audit trail record.

Persisted append-only (INSERT-only DB role) per
.claude/skills/observability-audit/SKILL.md. Never includes a password,
raw token, or password hash in `metadata`.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

_FORBIDDEN_METADATA_KEYS = {"password", "password_hash", "token", "raw_secret", "refresh_token"}


class UnsafeAuditMetadataError(ValueError):
    """Raised if metadata contains a key that looks like a secret."""


@dataclass(frozen=True, slots=True)
class AuditRecord:
    action: str
    target_type: str
    target_id: str
    outcome: str  # "success" | "failure"
    correlation_id: str
    actor_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    audit_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.outcome not in ("success", "failure"):
            raise ValueError("outcome must be 'success' or 'failure'.")
        offending = _FORBIDDEN_METADATA_KEYS & self.metadata.keys()
        if offending:
            raise UnsafeAuditMetadataError(
                f"Audit metadata must never contain: {sorted(offending)}."
            )
