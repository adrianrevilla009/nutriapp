"""Password value object.

Holds plaintext only transiently, in memory, for the duration of
registration/change-password validation and hashing. Never persisted,
never logged (CLAUDE.md rule: never log passwords, tokens, or hashes).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_MIN_LENGTH = 12
_HAS_UPPER = re.compile(r"[A-Z]")
_HAS_LOWER = re.compile(r"[a-z]")
_HAS_DIGIT = re.compile(r"\d")
_HAS_SYMBOL = re.compile(r"[^A-Za-z0-9]")


class WeakPasswordError(ValueError):
    """Raised when a candidate password fails the domain strength policy."""


@dataclass(frozen=True, slots=True)
class Password:
    """A plaintext password that has passed the domain strength policy.

    Policy: minimum length 12, and at least three of the four character
    classes (upper, lower, digit, symbol). This is a deliberately
    conservative default for a health-data-adjacent product; revisit only
    via an explicit decision, not silently.
    """

    plaintext: str

    def __post_init__(self) -> None:
        if len(self.plaintext) < _MIN_LENGTH:
            raise WeakPasswordError(f"Password must be at least {_MIN_LENGTH} characters long.")
        classes_present = sum(
            1
            for pattern in (_HAS_UPPER, _HAS_LOWER, _HAS_DIGIT, _HAS_SYMBOL)
            if pattern.search(self.plaintext)
        )
        if classes_present < 3:
            raise WeakPasswordError(
                "Password must contain at least 3 of: uppercase, lowercase, digit, symbol."
            )

    def __repr__(self) -> str:
        return "Password(***redacted***)"

    def __str__(self) -> str:
        return "***redacted***"
