"""Application-layer error types."""

from __future__ import annotations


class SendNotificationFailedError(Exception):
    """Raised when a transactional-email command could not complete a send
    (reveal failure or provider failure) -- the consumer's dead-letter path
    (messaging-conventions SKILL.md) acts on this, it is never swallowed."""


class InvalidPreferenceUpdateError(ValueError):
    """Raised when a preferences update targets an invalid category or an
    invalid quiet-hours window (e.g. a transactional category, or a
    malformed window)."""
