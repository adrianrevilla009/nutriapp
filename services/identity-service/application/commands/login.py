"""LoginCommand + handler.

Issues a short-lived RS256 access token (user_id + roles) and a revocable
refresh token (ADR-0022). Rejects with a single generic error shape for
every failure reason (no user-enumeration signal) while writing the
specific reason to the audit trail only.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from application.errors import InvalidCredentialsError, RateLimitedError
from application.security.token_generation import generate_opaque_secret, hash_secret
from domain.entities.audit_record import AuditRecord
from domain.entities.token import RefreshToken
from domain.entities.user import AccountLockedError, EmailNotVerifiedError
from domain.events.new_device_login_detected import build_new_device_login_detected_event
from domain.ports.audit_repository_port import AuditRepositoryPort
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.ports.password_hasher_port import PasswordHasherPort
from domain.ports.rate_limiter_port import RateLimiterPort, RateLimitExceededError
from domain.ports.token_issuer_port import TokenIssuerPort
from domain.ports.token_repository_port import TokenRepositoryPort
from domain.ports.user_repository_port import UserRepositoryPort
from domain.value_objects.device_fingerprint import DeviceFingerprint
from domain.value_objects.email import Email, InvalidEmailError

REFRESH_TOKEN_TTL = timedelta(days=30)
LOGIN_RATE_LIMIT = 10
LOGIN_RATE_LIMIT_WINDOW_SECONDS = 60
# A fixed, never-matching hash used to keep verify() timing similar whether
# or not the email exists — avoids a trivial user-enumeration timing oracle.
_DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$"
    "AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
)


@dataclass(frozen=True, slots=True)
class LoginCommand:
    email: str
    password: str
    correlation_id: str
    client_ip: str
    user_agent: str


@dataclass(frozen=True, slots=True)
class LoginResult:
    access_token: str
    refresh_token: str
    user_id: uuid.UUID


class LoginHandler:
    def __init__(
        self,
        user_repository: UserRepositoryPort,
        token_repository: TokenRepositoryPort,
        outbox_repository: OutboxRepositoryPort,
        password_hasher: PasswordHasherPort,
        token_issuer: TokenIssuerPort,
        rate_limiter: RateLimiterPort,
        audit_repository: AuditRepositoryPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._users = user_repository
        self._tokens = token_repository
        self._outbox = outbox_repository
        self._password_hasher = password_hasher
        self._token_issuer = token_issuer
        self._rate_limiter = rate_limiter
        self._audit = audit_repository
        self._now_fn = now_fn

    async def handle(self, command: LoginCommand) -> LoginResult:
        try:
            await self._rate_limiter.check_and_increment(
                key=f"identity:ratelimit:login:{command.client_ip}",
                limit=LOGIN_RATE_LIMIT,
                window_seconds=LOGIN_RATE_LIMIT_WINDOW_SECONDS,
            )
        except RateLimitExceededError as exc:
            await self._audit_failure(command, reason="rate_limited")
            raise RateLimitedError("Too many login attempts.") from exc

        try:
            email = Email(command.email)
        except InvalidEmailError:
            self._password_hasher.verify(command.password, _DUMMY_PASSWORD_HASH)
            await self._audit_failure(command, reason="unknown_email")
            raise InvalidCredentialsError("Invalid email or password.")

        user = await self._users.get_by_email(email)
        if user is None:
            self._password_hasher.verify(command.password, _DUMMY_PASSWORD_HASH)
            await self._audit_failure(command, reason="unknown_email")
            raise InvalidCredentialsError("Invalid email or password.")

        try:
            user.ensure_can_attempt_login()
        except AccountLockedError:
            await self._audit_failure(command, reason="account_locked", user=user)
            raise InvalidCredentialsError("Invalid email or password.")
        except EmailNotVerifiedError:
            await self._audit_failure(command, reason="email_not_verified", user=user)
            raise InvalidCredentialsError("Invalid email or password.")

        if not self._password_hasher.verify(command.password, user.password_hash):
            user.record_login_failure()
            await self._users.save(user)
            await self._audit_failure(command, reason="wrong_password", user=user)
            raise InvalidCredentialsError("Invalid email or password.")

        fingerprint = DeviceFingerprint.from_request_context(command.user_agent, command.client_ip)
        is_first_login = user.is_first_login()
        is_known_device = user.is_known_device(fingerprint.hash_value)
        user.record_login_success()
        user.remember_device(fingerprint.hash_value)
        await self._users.save(user)

        now = self._now_fn()
        access_token = self._token_issuer.issue_access_token(user.user_id, user.roles)
        raw_refresh_secret = generate_opaque_secret()
        refresh_token = RefreshToken(
            token_id=uuid.uuid4(),
            user_id=user.user_id,
            token_hash=hash_secret(raw_refresh_secret),
            created_at=now,
            expires_at=now + REFRESH_TOKEN_TTL,
        )
        await self._tokens.save_refresh_token(refresh_token)

        await self._audit.record(
            AuditRecord(
                action="login",
                target_type="user",
                target_id=str(user.user_id),
                outcome="success",
                correlation_id=command.correlation_id,
                actor_id=str(user.user_id),
            )
        )

        if not is_first_login and not is_known_device:
            event = build_new_device_login_detected_event(
                user_id=user.user_id,
                device_fingerprint_hash=fingerprint.hash_value,
                occurred_at_iso=now.isoformat(),
                email=str(user.email),
                correlation_id=command.correlation_id,
            )
            await self._outbox.enqueue(event)

        return LoginResult(
            access_token=access_token,
            refresh_token=raw_refresh_secret,
            user_id=user.user_id,
        )

    async def _audit_failure(self, command: LoginCommand, *, reason: str, user=None) -> None:
        await self._audit.record(
            AuditRecord(
                action="login",
                target_type="user",
                target_id=str(user.user_id) if user else command.email,
                outcome="failure",
                correlation_id=command.correlation_id,
                actor_id=str(user.user_id) if user else None,
                metadata={"reason": reason},
            )
        )
