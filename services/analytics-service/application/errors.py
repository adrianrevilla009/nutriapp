"""Application-layer error types, mapped to HTTP status codes in
infrastructure/http/error_mapping.py -- own local copy per service
(CLAUDE.md section 2.5), mirrors recipe-service's/social-service's
errors.py shape."""

from __future__ import annotations


class NotEntitledError(Exception):
    """Raised when a Pro-gated action (report/export) is attempted by a
    user who is not entitled. Mapped to 402/NOT_ENTITLED
    (infrastructure/http/error_mapping.py), reusing recipe-service's
    convention verbatim."""


class InvalidReportRequestError(Exception):
    """Raised for a malformed/out-of-bounds report request (e.g. a window
    exceeding the maximum allowed range)."""
