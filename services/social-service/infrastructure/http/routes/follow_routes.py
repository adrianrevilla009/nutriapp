"""Follow/unfollow/listing routes -- `POST /api/v1/social/follows`,
`DELETE /api/v1/social/follows/{followee_id}`,
`GET /api/v1/social/follows/following`, `GET /api/v1/social/follows/followers`
(implementation plan section 1). JWT-authenticated via
packages/shared-contracts' centralized dependency. Follow/unfollow are
Pro-gated; the two list routes are not (implementation plan section 1's
acceptance criteria 1-3)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.follow_user import FollowUserCommand, FollowUserHandler
from application.commands.unfollow_user import UnfollowUserCommand, UnfollowUserHandler
from application.queries.list_followers import ListFollowersHandler, ListFollowersQuery
from application.queries.list_following import ListFollowingHandler, ListFollowingQuery
from infrastructure.composition_root import Container, build_repositories
from infrastructure.http.dependencies import (
    get_authenticated_user_id,
    get_container,
    get_correlation_id,
    get_session,
)
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.social_schemas import (
    FollowListResponse,
    FollowRequest,
    FollowResponse,
    follow_to_response,
)

router = APIRouter(prefix="/api/v1/social", tags=["social"])


@router.post(
    "/follows",
    response_model=FollowResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Follow another user (Pro-gated, idempotent)",
)
async def follow_user(
    body: FollowRequest,
    user_id: Annotated[uuid.UUID, Depends(get_authenticated_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[Container, Depends(get_container)],
    correlation_id: Annotated[str, Depends(get_correlation_id)],
) -> FollowResponse | JSONResponse:
    follows, _feed, cache, outbox = build_repositories(session)
    handler = FollowUserHandler(follows, cache, container.entitlement_check, outbox)
    try:
        follow = await handler.handle(
            FollowUserCommand(
                follower_id=user_id, followee_id=body.followee_id, correlation_id=correlation_id
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)
    return follow_to_response(follow)


@router.delete(
    "/follows/{followee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Unfollow a user (Pro-gated, idempotent, hard delete)",
)
async def unfollow_user(
    followee_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_authenticated_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[Container, Depends(get_container)],
    correlation_id: Annotated[str, Depends(get_correlation_id)],
) -> Response | JSONResponse:
    follows, _feed, cache, outbox = build_repositories(session)
    handler = UnfollowUserHandler(follows, cache, container.entitlement_check, outbox)
    try:
        await handler.handle(
            UnfollowUserCommand(
                follower_id=user_id, followee_id=followee_id, correlation_id=correlation_id
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/follows/following",
    response_model=FollowListResponse,
    summary="List who you follow (not Pro-gated)",
)
async def list_following(
    user_id: Annotated[uuid.UUID, Depends(get_authenticated_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FollowListResponse:
    follows, _feed, _cache, _outbox = build_repositories(session)
    handler = ListFollowingHandler(follows)
    results = await handler.handle(ListFollowingQuery(user_id=user_id))
    return FollowListResponse(items=[follow_to_response(f) for f in results])


@router.get(
    "/follows/followers",
    response_model=FollowListResponse,
    summary="List your followers (not Pro-gated)",
)
async def list_followers(
    user_id: Annotated[uuid.UUID, Depends(get_authenticated_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FollowListResponse:
    follows, _feed, _cache, _outbox = build_repositories(session)
    handler = ListFollowersHandler(follows)
    results = await handler.handle(ListFollowersQuery(user_id=user_id))
    return FollowListResponse(items=[follow_to_response(f) for f in results])
