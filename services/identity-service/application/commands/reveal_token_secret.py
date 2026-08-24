"""RevealTokenSecretCommand + handler.

Backs the internal `POST /internal/v1/auth/tokens/{reference_id}/reveal`
endpoint (implementation plan section 5), called once by
notification-service to retrieve the raw email-verification/password-reset
secret so it can build the link in the outbound email. Never routed
through Kong (implementation plan section 6). The caller wraps this call
in a circuit breaker on its own side.
"""
from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from application.errors import InvalidCallerCredentialError, InvalidTokenError
from domain.entities.audit_record import AuditRecord
from domain.entities.token import (
    SecretTokenKind,
    TokenAlreadyRevealedError,
    TokenExpiredError,
)
from domain.ports.audit_repository_port import AuditRepositoryPort
from domain.ports.token_repository_port import TokenRepositoryPort

_INVALID_REVEAL_ERRORS = (TokenAlreadyRevealedError, TokenExpiredError)


@dataclass(frozen=True, slots=True)
class RevealTokenSecretCommand:
    reference_id: str
    caller_service_credential: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class RevealTokenSecretResult:
    secret: str
    user_id: uuid.UUID
    kind: SecretTokenKind


class RevealTokenSecretHandler:
    def __init__(
        self,
        token_repository: TokenRepositoryPort,
        audit_repository: AuditRepositoryPort,
        expected_caller_credential: str,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._tokens = token_repository
        self._audit = audit_repository
        self._expected_caller_credential = expected_caller_credential
        self._now_fn = now_fn

    async def handle(self, command: RevealTokenSecretCommand) -> RevealTokenSecretResult:
        if not hmac.compare_digest(
            command.caller_service_credential, self._expected_caller_credential
        ):
            await self._audit.record(
                AuditRecord(
                    action="token_reveal",
                    target_type="secret_token",
                    target_id=command.reference_id,
                    outcome="failure",
                    correlation_id=command.correlation_id,
                    metadata={"reason": "invalid_caller_credential"},
                )
            )
            raise InvalidCallerCredentialError("Invalid internal service credential.")

        now = self._now_fn()
        try:
            reference_id = uuid.UUID(command.reference_id)
            token = await self._tokens.get_secret_token(reference_id)
            if token is None:
                raise InvalidTokenError("Unknown token reference id.")

            secret = token.reveal(now)
            await self._tokens.save_secret_token(token)
        except (InvalidTokenError, *_INVALID_REVEAL_ERRORS, ValueError) as exc:
            await self._audit.record(
                AuditRecord(
                    action="token_reveal",
                    target_type="secret_token",
                    target_id=command.reference_id,
                    outcome="failure",
                    correlation_id=command.correlation_id,
                    metadata={"reason": type(exc).__name__},
                )
            )
            raise InvalidTokenError("Token cannot be revealed.") from exc

        await self._audit.record(
            AuditRecord(
                action="token_reveal",
                target_type="secret_token",
                target_id=str(token.reference_id),
                outcome="success",
                correlation_id=command.correlation_id,
                actor_id=str(token.user_id),
            )
        )
        return RevealTokenSecretResult(
            secret=secret, user_id=token.user_id, kind=token.kind
        )
