"""POST /internal/v1/auth/tokens/{reference_id}/reveal — internal-only,
never routed through Kong (implementation plan section 6). Called once by
notification-service to retrieve the raw verification/reset secret. The
caller wraps this call in a circuit breaker on its own side
(resilience-patterns SKILL.md).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.reveal_token_secret import (
    RevealTokenSecretCommand,
    RevealTokenSecretHandler,
)
from infrastructure.composition_root import Container, build_repositories
from infrastructure.http.dependencies import (
    get_audit_session,
    get_container,
    get_correlation_id,
    get_session,
)
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.internal_schemas import RevealTokenResponse

router = APIRouter(prefix="/internal/v1/auth/tokens", tags=["internal"])


@router.post(
    "/{reference_id}/reveal",
    response_model=RevealTokenResponse,
    summary="Reveal a secret-reference token's raw secret (internal, once-only)",
    description="Service-to-service only. Never routed through Kong. Every attempt, "
    "success or failure, writes an audit record.",
)
async def reveal_token(
    reference_id: str,
    session: AsyncSession = Depends(get_session),
    audit_session: AsyncSession = Depends(get_audit_session),
    container: Container = Depends(get_container),
    correlation_id: str = Depends(get_correlation_id),
    x_internal_service_credential: str = Header(default=""),
):
    _users, tokens, _outbox, audit = build_repositories(session, audit_session)
    handler = RevealTokenSecretHandler(tokens, audit, container.settings.internal_reveal_credential)
    try:
        result = await handler.handle(
            RevealTokenSecretCommand(
                reference_id=reference_id,
                caller_service_credential=x_internal_service_credential,
                correlation_id=correlation_id,
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return RevealTokenResponse(secret=result.secret, user_id=result.user_id, kind=result.kind.value)
