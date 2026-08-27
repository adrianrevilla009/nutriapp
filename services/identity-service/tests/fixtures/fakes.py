"""In-memory fake port implementations for application-layer unit tests
(hexagonal-architecture SKILL.md: "Application: unit tests using
fake/in-memory implementations of ports, not the real adapters").
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from domain.entities.audit_record import AuditRecord
from domain.entities.token import RefreshToken, SecretReferenceToken, SecretTokenKind
from domain.entities.user import User
from domain.events.base import DomainEvent
from domain.ports.rate_limiter_port import RateLimiterUnavailableError, RateLimitExceededError
from domain.value_objects.email import Email
from domain.value_objects.password import Password


class FakeUserRepository:
    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, User] = {}

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._by_id.get(user_id)

    async def get_by_email(self, email: Email) -> User | None:
        for user in self._by_id.values():
            if str(user.email) == str(email):
                return user
        return None

    async def save(self, user: User) -> None:
        self._by_id[user.user_id] = user


class FakeTokenRepository:
    def __init__(self) -> None:
        self.refresh_tokens: dict[uuid.UUID, RefreshToken] = {}
        self.secret_tokens: dict[uuid.UUID, SecretReferenceToken] = {}

    async def save_refresh_token(self, token: RefreshToken) -> None:
        self.refresh_tokens[token.token_id] = token

    async def get_refresh_token(self, token_id: uuid.UUID) -> RefreshToken | None:
        return self.refresh_tokens.get(token_id)

    async def get_refresh_token_by_hash(self, token_hash: str) -> RefreshToken | None:
        for token in self.refresh_tokens.values():
            if token.token_hash == token_hash:
                return token
        return None

    async def revoke_all_refresh_tokens_for_user(self, user_id: uuid.UUID) -> None:
        for token in self.refresh_tokens.values():
            if token.user_id == user_id:
                token.revoke(datetime.now(timezone.utc))

    async def save_secret_token(self, token: SecretReferenceToken) -> None:
        self.secret_tokens[token.reference_id] = token

    async def get_secret_token(self, reference_id: uuid.UUID) -> SecretReferenceToken | None:
        return self.secret_tokens.get(reference_id)

    async def get_latest_secret_token_for_user(
        self, user_id: uuid.UUID, kind: SecretTokenKind
    ) -> SecretReferenceToken | None:
        candidates = [
            t for t in self.secret_tokens.values() if t.user_id == user_id and t.kind == kind
        ]
        return max(candidates, key=lambda t: t.created_at, default=None)


class FakeOutboxRepository:
    def __init__(self) -> None:
        self.enqueued: list[DomainEvent] = []
        self.published_ids: set[uuid.UUID] = set()

    async def enqueue(self, event: DomainEvent) -> None:
        self.enqueued.append(event)

    async def fetch_unpublished(self, limit: int = 100) -> list[DomainEvent]:
        return [e for e in self.enqueued if e.event_id not in self.published_ids][:limit]

    async def mark_published(self, event_id: uuid.UUID) -> None:
        self.published_ids.add(event_id)


class FakeAuditRepository:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, entry: AuditRecord) -> None:
        self.records.append(entry)


class FakePasswordHasher:
    """Deterministic fake — NOT for production use, argon2 only in
    infrastructure/security/argon2_password_hasher.py."""

    def hash(self, password: Password) -> str:
        return f"hashed:{password.plaintext}"

    def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == f"hashed:{password}"


class FakeTokenIssuer:
    def issue_access_token(self, user_id: uuid.UUID, roles) -> str:
        role_list = ",".join(sorted(r.value for r in roles))
        return f"access-token:{user_id}:{role_list}"

    def get_jwks(self) -> dict:
        return {"keys": []}


class FakeRateLimiter:
    """Configurable fake: allow by default; can be told to reject or fail closed."""

    def __init__(self) -> None:
        self.should_exceed = False
        self.should_be_unavailable = False
        self.calls: list[str] = []

    async def check_and_increment(self, key: str, limit: int, window_seconds: int) -> None:
        self.calls.append(key)
        if self.should_be_unavailable:
            raise RateLimiterUnavailableError("Redis unreachable.")
        if self.should_exceed:
            raise RateLimitExceededError("Rate limit exceeded.")
