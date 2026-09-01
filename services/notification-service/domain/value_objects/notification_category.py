"""NotificationCategory -- a channel-scoped category value object.

Enforces the transactional/non-transactional split from
docs/notifications.md section 1 at the type level: an email
(transactional) category can never be constructed as a push category and
vice versa (test-plan section 1). Transactional email categories are
never suppressible by preference or quiet hours (is_transactional).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Channel(str, Enum):
    EMAIL = "email"
    PUSH = "push"


class InvalidNotificationCategoryError(ValueError):
    """Raised when a category name is not valid for the given channel."""


PUSH_CATEGORIES: frozenset[str] = frozenset({"fasting", "meal", "water", "new_follower"})
EMAIL_CATEGORIES: frozenset[str] = frozenset({"verification", "password_reset", "new_device_alert"})


@dataclass(frozen=True, slots=True)
class NotificationCategory:
    name: str
    channel: Channel

    def __post_init__(self) -> None:
        valid = PUSH_CATEGORIES if self.channel is Channel.PUSH else EMAIL_CATEGORIES
        if self.name not in valid:
            raise InvalidNotificationCategoryError(
                f"{self.name!r} is not a valid {self.channel.value} category."
            )

    @classmethod
    def push(cls, name: str) -> NotificationCategory:
        return cls(name=name, channel=Channel.PUSH)

    @classmethod
    def email(cls, name: str) -> NotificationCategory:
        return cls(name=name, channel=Channel.EMAIL)

    @property
    def is_transactional(self) -> bool:
        return self.channel is Channel.EMAIL
