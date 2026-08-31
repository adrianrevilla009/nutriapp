"""Activity feed route -- `GET /api/v1/social/feed` (implementation plan
section 1). Pro-gated. Fan-out-on-read: joins the caller's own `follows`
table against the local `feed_entries` projection (never a synchronous
call to recipe-service, implementation plan section 1.8)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from application.queries.get_feed import GetFeedHandler, GetFeedQuery
from infrastructure.composition_root import Container, build_repositories
from infrastructure.http.dependencies import get_authenticated_user_id, get_container, get_session
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.social_schemas import FeedResponse, feed_entry_to_response

router = APIRouter(prefix="/api/v1/social", tags=["social"])


@router.get(
    "/feed",
    response_model=FeedResponse,
    summary="Activity feed of followed users' published recipes (Pro-gated)",
    description="Entitlement is checked before any repository query is attempted. Never "
    "includes an entry from an author the caller does not follow, or an unpublished recipe.",
)
async def get_feed(
    user_id: Annotated[uuid.UUID, Depends(get_authenticated_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[Container, Depends(get_container)],
) -> FeedResponse | JSONResponse:
    follows, feed, cache, _outbox = build_repositories(session)
    handler = GetFeedHandler(feed, follows, cache, container.entitlement_check)
    try:
        entries = await handler.handle(GetFeedQuery(user_id=user_id))
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)
    return FeedResponse(items=[feed_entry_to_response(e) for e in entries])
