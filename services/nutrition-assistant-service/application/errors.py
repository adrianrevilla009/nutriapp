"""Application-layer error types -- never leak a raw adapter exception
(ConversationUnavailableError, VectorStoreUnavailableError, ...) past the
application boundary; HTTP-layer error_mapping.py maps these to response
codes."""

from __future__ import annotations


class NotEntitledError(Exception):
    """The requesting user is not Pro-entitled for the chat feature."""


class AssistantUnavailableError(Exception):
    """The LLM provider is unavailable (circuit open / persistent
    failure). Distinct from a normal insufficient-context response --
    never presented as if it were a real (if empty) answer."""
