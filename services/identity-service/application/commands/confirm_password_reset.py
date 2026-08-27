"""ConfirmPasswordResetCommand + handler."""

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
from domain.ports.audit_repository_port import AuditRepositoryPort
from domain.ports.password_hasher_port import PasswordHasherPort
from domain.ports.token_repository_port import TokenRepositoryPort
from domain.ports.user_repository_port import UserRepositoryPort
from domain.value_objects.password import Password

_INVALID_TOKEN_ERRORS = (TokenAlreadyUsedError, TokenExpiredError, TokenSecretMismatchError)


@dataclass(frozen=True, slots=True)
class ConfirmPasswordResetCommand:
    reference_id: str
    secret: str
    new_password: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class ConfirmPasswordResetResult:
    user_id: uuid.UUID


class ConfirmPasswordResetHandler:
    def __init__(
        self,
        user_repository: UserRepositoryPort,
        token_repository: TokenRepositoryPort,
        password_hasher: PasswordHasherPort,
        audit_repository: AuditRepositoryPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._users = user_repository
        self._tokens = token_repository
        self._password_hasher = password_hasher
        self._audit = audit_repository
        self._now_fn = now_fn

    async def handle(self, command: ConfirmPasswordResetCommand) -> ConfirmPasswordResetResult:
        # Weak password is rejected before any repository call.
        new_password = Password(command.new_password)

        now = self._now_fn()
        try:
            reference_id = uuid.UUID(command.reference_id)
            token = await self._tokens.get_secret_token(reference_id)
            if token is None or token.kind != SecretTokenKind.PASSWORD_RESET:
                raise InvalidTokenError("Unknown password reset token.")

            user = await self._users.get_by_id(token.user_id)
            if user is None:
                raise InvalidTokenError("Unknown password reset token.")

            token.verify_and_mark_used(hash_secret(command.secret), now)

            new_hash = self._password_hasher.hash(new_password)
            user.change_password(new_hash)

            await self._tokens.save_secret_token(token)
            await self._users.save(user)
            await self._tokens.revoke_all_refresh_tokens_for_user(user.user_id)
        except (InvalidTokenError, *_INVALID_TOKEN_ERRORS, ValueError) as exc:
            await self._audit.record(
                AuditRecord(
                    action="password_change",
                    target_type="user",
                    target_id=command.reference_id,
                    outcome="failure",
                    correlation_id=command.correlation_id,
                    metadata={"reason": type(exc).__name__},
                )
            )
            raise InvalidTokenError("Invalid or expired password reset token.") from exc

        await self._audit.record(
            AuditRecord(
                action="password_change",
                target_type="user",
                target_id=str(user.user_id),
                outcome="success",
                correlation_id=command.correlation_id,
                actor_id=str(user.user_id),
            )
        )
        return ConfirmPasswordResetResult(user_id=user.user_id)
