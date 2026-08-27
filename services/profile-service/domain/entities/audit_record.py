"""Immutable audit trail record -- profile-service's first audit-trail
capability (implementation plan Addendum 2, requirement 6).

Persisted append-only (INSERT-only DB role, `profile_service_audit_writer`
-- see migrations/versions/0003_create_audit_records_table.py and
.claude/skills/observability-audit/SKILL.md). This service discloses
Article 9 special-category biometric/health data outside its own boundary
exactly once (`POST /internal/v1/profile/{user_id}/reveal-metrics`) --
every call to that endpoint, success or failure, writes exactly one of
these. `metadata` must never contain a raw biometric field VALUE (weight,
height, age, sex, activity level, goal type/target) -- only field NAMES
(e.g. `{"fields": ["weight_kg", ...]}`) or a short, generic failure
`reason` string. `__post_init__` enforces this at construction time as a
defense-in-depth backstop, not just a code-review convention.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# Any of these keys would smuggle an actual biometric VALUE into the audit
# trail (as opposed to a field NAME, which `metadata["fields"]` legitimately
# carries as a list of strings) -- forbidden regardless of nesting depth at
# the top level of `metadata`.
_FORBIDDEN_METADATA_KEYS = {
    "weight_kg",
    "height_cm",
    "age",
    "sex",
    "activity_level",
    "goal_type",
    "value",
    "target_value",
}


class UnsafeAuditMetadataError(ValueError):
    """Raised if metadata contains a key that looks like a biometric value."""


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
                f"Audit metadata must never contain a biometric value key: {sorted(offending)}."
            )
