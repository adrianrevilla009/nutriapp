"""Application-layer errors -- mapped to HTTP responses by
`infrastructure.http.error_mapping` (api-conventions SKILL.md)."""

from __future__ import annotations


class InvalidImageError(ValueError):
    """Raised when the uploaded payload is empty or not a supported image
    content type. Mapped to `422 Unprocessable Entity` -- distinct from a
    provider/lookup failure (`status="unavailable"` in the 200 response
    body), which is a designed fallback, not a client error."""
