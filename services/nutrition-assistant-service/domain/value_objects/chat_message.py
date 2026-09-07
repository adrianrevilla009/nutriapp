"""ChatMessage -- one turn of the client-supplied chat history
(implementation plan section 1: no server-side conversation persistence
this pass, the caller supplies its own history on every request).
Frozen/immutable per hexagonal-architecture SKILL.md's value-object rule."""

from __future__ import annotations

from dataclasses import dataclass

_VALID_ROLES = frozenset({"user", "assistant"})


class InvalidChatMessageError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: str
    content: str

    def __post_init__(self) -> None:
        if not self.role or not self.role.strip():
            raise InvalidChatMessageError("ChatMessage.role must not be empty.")
        if self.role not in _VALID_ROLES:
            raise InvalidChatMessageError(
                f"ChatMessage.role must be one of {sorted(_VALID_ROLES)}, got {self.role!r}."
            )
        if not self.content or not self.content.strip():
            raise InvalidChatMessageError("ChatMessage.content must not be empty.")
