"""RegisterUserCommand + handler.

Orchestrates: strength/format validation -> duplicate-email check ->
password hashing -> persistence -> email-verification token issuance ->
UserRegistered enqueued to the outbox, all in the application layer,
depending only on domain objects and ports (hexagonal-architecture SKILL.md).
"""
from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from application.security.token_generation import generate_opaque_secret, hash_secret
from domain.entities.token import SecretReferenceToken, SecretTokenKind
from domain.entities.user import User
from domain.events.user_registered import build_user_registered_event
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.ports.password_hasher_port import PasswordHasherPort
from domain.ports.rate_limiter_port import RateLimiterPort
from domain.ports.token_repository_port import TokenRepositoryPort
from domain.ports.user_repository_port import UserRepositoryPort
from domain.services.registration_policy import RegistrationPolicy
from domain.value_objects.email import Email
from domain.value_objects.password import Password

EMAIL_VERIFICATION_TOKEN_TTL = timedelta(hours=24)
REGISTER_RATE_LIMIT = 5
REGISTER_RATE_LIMIT_WINDOW_SECONDS = 60


@dataclass(frozen=True, slots=True)
class RegisterUserCommand:
    email: str
    password: str
    correlation_id: str
    client_ip: str


@dataclass(frozen=True, slots=True)
class RegisterUserResult:
    user_id: uuid.UUID


class RegisterUserHandler:
    def __init__(
        self,
        user_repository: UserRepositoryPort,
        token_repository: TokenRepositoryPort,
        outbox_repository: OutboxRepositoryPort,
        password_hasher: PasswordHasherPort,
        rate_limiter: RateLimiterPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._users = user_repository
        self._tokens = token_repository
        self._outbox = outbox_repository
        self._password_hasher = password_hasher
        self._rate_limiter = rate_limiter
        self._now_fn = now_fn

    async def handle(self, command: RegisterUserCommand) -> RegisterUserResult:
        await self._rate_limiter.check_and_increment(
            key=f"identity:ratelimit:register:{command.client_ip}",
            limit=REGISTER_RATE_LIMIT,
            window_seconds=REGISTER_RATE_LIMIT_WINDOW_SECONDS,
        )

        email = Email(command.email)
        password = Password(command.password)

        existing = await self._users.get_by_email(email)
        RegistrationPolicy.ensure_email_available(email, existing)

        password_hash = self._password_hasher.hash(password)
        user = User.register(email, password_hash)
        await self._users.save(user)

        now = self._now_fn()
        raw_secret = generate_opaque_secret()
        token = SecretReferenceToken(
            reference_id=uuid.uuid4(),
            user_id=user.user_id,
            kind=SecretTokenKind.EMAIL_VERIFICATION,
            secret_hash=hash_secret(raw_secret),
            created_at=now,
            expires_at=now + EMAIL_VERIFICATION_TOKEN_TTL,
            raw_secret=raw_secret,
        )
        await self._tokens.save_secret_token(token)

        event = build_user_registered_event(
            user_id=user.user_id,
            email=str(user.email),
            registered_at_iso=user.created_at.isoformat(),
            email_verification_token_reference_id=token.reference_id,
            correlation_id=command.correlation_id,
        )
        await self._outbox.enqueue(event)

        return RegisterUserResult(user_id=user.user_id)
