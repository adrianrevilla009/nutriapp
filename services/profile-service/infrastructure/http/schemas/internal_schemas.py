"""Response schema for the internal, non-Kong-routed
`POST /internal/v1/profile/{user_id}/reveal-metrics` endpoint
(implementation plan Addendum 2). Exactly the 6 allow-listed fields --
response minimization (requirement 5)."""

from __future__ import annotations

from pydantic import BaseModel


class BiometricSnapshotRevealResponse(BaseModel):
    weight_kg: float | None
    height_cm: float | None
    age: int | None
    sex: str | None
    activity_level: str | None
    goal_type: str | None
