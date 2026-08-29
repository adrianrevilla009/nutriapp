"""Application-layer errors -- mapped to HTTP responses by
`infrastructure.http.error_mapping` (api-conventions SKILL.md)."""

from __future__ import annotations


class ExerciseEntryNotFoundError(LookupError):
    """Raised when no entry exists for the given (entry_id, user_id) pair.
    Never distinguishes "exists but belongs to another user" from
    "doesn't exist at all" in its message or HTTP mapping -- both map to
    404 (test-plan section 3: "never leak existence of another user's
    entry via a 403 vs 404 distinction")."""


class ExerciseEntryAlreadyDeletedError(ValueError):
    """Raised when an update is attempted against a soft-deleted entry --
    a deleted entry can no longer be corrected (test-plan section 1)."""
