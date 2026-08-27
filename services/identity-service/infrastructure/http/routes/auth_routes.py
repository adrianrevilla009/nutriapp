"""POST /api/v1/auth/* routes. Thin controllers only — parse request into a
command DTO, call the application handler, serialize the result
(api-conventions SKILL.md). No business logic here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.confirm_password_reset import (
    ConfirmPasswordResetCommand,
    ConfirmPasswordResetHandler,
)
from application.commands.login import LoginCommand, LoginHandler
from application.commands.logout import LogoutCommand, LogoutHandler
from application.commands.refresh_access_token import (
    RefreshAccessTokenCommand,
    RefreshAccessTokenHandler,
)
from application.commands.register_user import RegisterUserCommand, RegisterUserHandler
from application.commands.request_password_reset import (
    RequestPasswordResetCommand,
    RequestPasswordResetHandler,
)
from application.commands.verify_email import VerifyEmailCommand, VerifyEmailHandler
from infrastructure.composition_root import Container, build_repositories
from infrastructure.http.dependencies import (
    get_audit_session,
    get_client_ip,
    get_container,
    get_correlation_id,
    get_session,
    get_user_agent,
)
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.auth_schemas import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    PasswordResetConfirmRequest,
    PasswordResetConfirmResponse,
    PasswordResetRequestRequest,
    PasswordResetRequestResponse,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    RegisterResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    summary="Register a new user",
    description="Creates a user (argon2-hashed password), publishes UserRegistered "
    "via the outbox, and issues an email-verification token reference id.",
)
async def register(
    body: RegisterRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
    correlation_id: str = Depends(get_correlation_id),
    client_ip: str = Depends(get_client_ip),
):
    users, tokens, outbox, _audit = build_repositories(session, session)  # audit unused here
    handler = RegisterUserHandler(
        users, tokens, outbox, container.password_hasher, container.rate_limiter
    )
    try:
        result = await handler.handle(
            RegisterUserCommand(
                email=body.email,
                password=body.password,
                correlation_id=correlation_id,
                client_ip=client_ip,
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001 — mapped centrally below
        await session.rollback()
        return map_exception(exc)
    return RegisterResponse(user_id=result.user_id)


@router.post(
    "/verify-email",
    response_model=VerifyEmailResponse,
    summary="Verify a user's email",
    description="Confirms a user's email via a time-limited, single-use token.",
)
async def verify_email(
    body: VerifyEmailRequest,
    session: AsyncSession = Depends(get_session),
    audit_session: AsyncSession = Depends(get_audit_session),
    correlation_id: str = Depends(get_correlation_id),
):
    users, tokens, _outbox, audit = build_repositories(session, audit_session)
    handler = VerifyEmailHandler(users, tokens, audit)
    try:
        result = await handler.handle(
            VerifyEmailCommand(
                reference_id=body.reference_id, secret=body.secret, correlation_id=correlation_id
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return VerifyEmailResponse(user_id=result.user_id)


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Authenticate and issue tokens",
    description="Issues a short-lived RS256 access token plus a revocable refresh "
    "token. Rejects bad credentials with a generic error.",
)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
    audit_session: AsyncSession = Depends(get_audit_session),
    container: Container = Depends(get_container),
    correlation_id: str = Depends(get_correlation_id),
    client_ip: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent),
):
    users, tokens, outbox, audit = build_repositories(session, audit_session)
    handler = LoginHandler(
        users,
        tokens,
        outbox,
        container.password_hasher,
        container.token_issuer,
        container.rate_limiter,
        audit,
    )
    try:
        result = await handler.handle(
            LoginCommand(
                email=body.email,
                password=body.password,
                correlation_id=correlation_id,
                client_ip=client_ip,
                user_agent=user_agent,
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return LoginResponse(access_token=result.access_token, refresh_token=result.refresh_token)


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="Exchange a refresh token for a new access token",
    description="No rotation-on-use for v1 — the refresh token itself is not reissued.",
)
async def refresh(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
    correlation_id: str = Depends(get_correlation_id),
):
    users, tokens, _outbox, _audit = build_repositories(session, session)  # audit unused here
    handler = RefreshAccessTokenHandler(tokens, users, container.token_issuer)
    try:
        result = await handler.handle(
            RefreshAccessTokenCommand(
                refresh_token=body.refresh_token, correlation_id=correlation_id
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return RefreshResponse(access_token=result.access_token)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Revoke the presented refresh token",
    description="Idempotent — safe to call twice.",
)
async def logout(
    body: LogoutRequest,
    session: AsyncSession = Depends(get_session),
    audit_session: AsyncSession = Depends(get_audit_session),
    correlation_id: str = Depends(get_correlation_id),
):
    _users, tokens, _outbox, audit = build_repositories(session, audit_session)
    handler = LogoutHandler(tokens, audit)
    try:
        result = await handler.handle(
            LogoutCommand(refresh_token=body.refresh_token, correlation_id=correlation_id)
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return LogoutResponse(revoked=result.revoked)


@router.post(
    "/password-reset/request",
    response_model=PasswordResetRequestResponse,
    summary="Request a password reset",
    description="Always responds 202 with the same body, regardless of whether the "
    "email exists — no user-enumeration signal.",
    status_code=202,
)
async def password_reset_request(
    body: PasswordResetRequestRequest,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
    correlation_id: str = Depends(get_correlation_id),
    client_ip: str = Depends(get_client_ip),
):
    users, tokens, outbox, _audit = build_repositories(session, session)  # audit unused here
    handler = RequestPasswordResetHandler(users, tokens, outbox, container.rate_limiter)
    try:
        await handler.handle(
            RequestPasswordResetCommand(
                email=body.email, correlation_id=correlation_id, client_ip=client_ip
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return PasswordResetRequestResponse()


@router.post(
    "/password-reset/confirm",
    response_model=PasswordResetConfirmResponse,
    summary="Confirm a password reset",
    description="Consumes a single-use reset token, updates the password, and "
    "revokes all existing refresh tokens for the user.",
)
async def password_reset_confirm(
    body: PasswordResetConfirmRequest,
    session: AsyncSession = Depends(get_session),
    audit_session: AsyncSession = Depends(get_audit_session),
    container: Container = Depends(get_container),
    correlation_id: str = Depends(get_correlation_id),
):
    users, tokens, _outbox, audit = build_repositories(session, audit_session)
    handler = ConfirmPasswordResetHandler(users, tokens, container.password_hasher, audit)
    try:
        result = await handler.handle(
            ConfirmPasswordResetCommand(
                reference_id=body.reference_id,
                secret=body.secret,
                new_password=body.new_password,
                correlation_id=correlation_id,
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return PasswordResetConfirmResponse(user_id=result.user_id)
