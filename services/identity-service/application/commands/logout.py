"""LogoutCommand + handler. Idempotent: safe to call twice."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from application.security.token_generation import hash_secret
from domain.entities.audit_record import AuditRecord
from domain.ports.audit_repository_port import AuditRepositoryPort
from domain.ports.token_repository_port import TokenRepositoryPort


@dataclass(frozen=True, slots=True)
class LogoutCommand:
    refresh_token: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class LogoutResult:
    revoked: bool


class LogoutHandler:
    def __init__(
        self,
        token_repository: TokenRepositoryPort,
        audit_repository: AuditRepositoryPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._tokens = token_repository
        self._audit = audit_repository
        self._now_fn = now_fn

    async def handle(self, command: LogoutCommand) -> LogoutResult:
        token = await self._tokens.get_refresh_token_by_hash(
            hash_secret(command.refresh_token)
        )
        if token is None:
            # Unknown token: idempotent success, nothing to revoke, nothing to audit.
            return LogoutResult(revoked=False)

        was_already_revoked = token.is_revoked()
        token.revoke(self._now_fn())
        await self._tokens.save_refresh_token(token)

        if not was_already_revoked:
            await self._audit.record(
                AuditRecord(
                    action="logout",
                    target_type="user",
                    target_id=str(token.user_id),
                    outcome="success",
                    correlation_id=command.correlation_id,
                    actor_id=str(token.user_id),
                )
            )
        return LogoutResult(revoked=True)
