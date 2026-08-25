"""Application-layer error types."""

from __future__ import annotations


class ProfileNotFoundError(Exception):
    """Raised when a query/command targets a user_id with no profile yet."""
