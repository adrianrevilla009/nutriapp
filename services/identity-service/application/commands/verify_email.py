"""VerifyEmailCommand + handler."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from application.errors import InvalidTokenError
from application.security.token_generation import hash_secret
from domain.entities.audit_record import AuditRecord
from domain.entities.token import (
    SecretTokenKind,
    TokenAlreadyUsedError,
    TokenExpiredError,
    TokenSecretMismatchError,
)
from domain.entities.user import AlreadyVerifiedError
from domain.ports.audit_repository_port import AuditRepositoryPort
from domain.ports.token_repository_port import TokenRepositoryPort
from domain.ports.user_repository_port import UserRepositoryPort

_INVALID_TOKEN_ERRORS = (
    TokenAlreadyUsedError,
    TokenExpiredError,
    TokenSecretMismatchError,
    AlreadyVerifiedError,
    ValueError,
)


@dataclass(frozen=True, slots=True)
class VerifyEmailCommand:
    reference_id: str
    secret: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class VerifyEmailResult:
    user_id: uuid.UUID


class VerifyEmailHandler:
    def __init__(
        self,
        user_repository: UserRepositoryPort,
        token_repository: TokenRepositoryPort,
        audit_repository: AuditRepositoryPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._users = user_repository
        self._tokens = token_repository
        self._audit = audit_repository
        self._now_fn = now_fn

    async def handle(self, command: VerifyEmailCommand) -> VerifyEmailResult:
        now = self._now_fn()
        try:
            reference_id = uuid.UUID(command.reference_id)
            token = await self._tokens.get_secret_token(reference_id)
            if token is None or token.kind != SecretTokenKind.EMAIL_VERIFICATION:
                raise InvalidTokenError("Unknown verification token.")

            user = await self._users.get_by_id(token.user_id)
            if user is None:
                raise InvalidTokenError("Unknown verification token.")

            token.verify_and_mark_used(hash_secret(command.secret), now)
            user.verify_email()

            await self._tokens.save_secret_token(token)
            await self._users.save(user)
        except (InvalidTokenError, *_INVALID_TOKEN_ERRORS) as exc:
            await self._audit.record(
                AuditRecord(
                    action="email_verified",
                    target_type="user",
                    target_id=command.reference_id,
                    outcome="failure",
                    correlation_id=command.correlation_id,
                    metadata={"reason": type(exc).__name__},
                )
            )
            raise InvalidTokenError("Invalid or expired verification token.") from exc

        await self._audit.record(
            AuditRecord(
                action="email_verified",
                target_type="user",
                target_id=str(user.user_id),
                outcome="success",
                correlation_id=command.correlation_id,
                actor_id=str(user.user_id),
            )
        )
        return VerifyEmailResult(user_id=user.user_id)
