"""RequestPasswordResetCommand + handler.

No user-enumeration signal: the response is identical in shape whether or
not the email exists, and no token/event is created for an unknown email.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from application.errors import RateLimitedError
from application.security.token_generation import generate_opaque_secret, hash_secret
from domain.entities.token import SecretReferenceToken, SecretTokenKind
from domain.events.password_reset_requested import build_password_reset_requested_event
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.ports.rate_limiter_port import RateLimiterPort, RateLimitExceededError
from domain.ports.token_repository_port import TokenRepositoryPort
from domain.ports.user_repository_port import UserRepositoryPort
from domain.value_objects.email import Email, InvalidEmailError

PASSWORD_RESET_TOKEN_TTL = timedelta(hours=1)
PASSWORD_RESET_RATE_LIMIT = 5
PASSWORD_RESET_RATE_LIMIT_WINDOW_SECONDS = 60


@dataclass(frozen=True, slots=True)
class RequestPasswordResetCommand:
    email: str
    correlation_id: str
    client_ip: str


@dataclass(frozen=True, slots=True)
class RequestPasswordResetResult:
    """Deliberately empty — same shape regardless of whether the account exists."""


class RequestPasswordResetHandler:
    def __init__(
        self,
        user_repository: UserRepositoryPort,
        token_repository: TokenRepositoryPort,
        outbox_repository: OutboxRepositoryPort,
        rate_limiter: RateLimiterPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._users = user_repository
        self._tokens = token_repository
        self._outbox = outbox_repository
        self._rate_limiter = rate_limiter
        self._now_fn = now_fn

    async def handle(self, command: RequestPasswordResetCommand) -> RequestPasswordResetResult:
        try:
            await self._rate_limiter.check_and_increment(
                key=f"identity:ratelimit:password-reset:{command.client_ip}",
                limit=PASSWORD_RESET_RATE_LIMIT,
                window_seconds=PASSWORD_RESET_RATE_LIMIT_WINDOW_SECONDS,
            )
        except RateLimitExceededError as exc:
            raise RateLimitedError("Too many password reset attempts.") from exc

        try:
            email = Email(command.email)
        except InvalidEmailError:
            return RequestPasswordResetResult()

        user = await self._users.get_by_email(email)
        if user is None:
            return RequestPasswordResetResult()

        now = self._now_fn()
        raw_secret = generate_opaque_secret()
        token = SecretReferenceToken(
            reference_id=uuid.uuid4(),
            user_id=user.user_id,
            kind=SecretTokenKind.PASSWORD_RESET,
            secret_hash=hash_secret(raw_secret),
            created_at=now,
            expires_at=now + PASSWORD_RESET_TOKEN_TTL,
            raw_secret=raw_secret,
        )
        await self._tokens.save_secret_token(token)

        event = build_password_reset_requested_event(
            user_id=user.user_id,
            email=str(user.email),
            reset_token_reference_id=token.reference_id,
            requested_at_iso=now.isoformat(),
            correlation_id=command.correlation_id,
        )
        await self._outbox.enqueue(event)

        return RequestPasswordResetResult()
