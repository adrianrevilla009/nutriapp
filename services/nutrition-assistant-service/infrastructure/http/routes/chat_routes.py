"""POST /api/v1/chat -- Pro-gated (implementation plan section 1
acceptance criterion 2, docs/api-catalog.md). `user_id` comes ONLY from
get_authenticated_user_id (the verified JWT) -- never from the request
body, which is what makes cross-user isolation structurally enforceable."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from application.queries.answer_chat_query import AnswerChatQueryCommand, AnswerChatQueryHandler
from domain.value_objects.chat_message import ChatMessage
from infrastructure.composition_root import Container, build_repositories
from infrastructure.http.dependencies import get_authenticated_user_id, get_container, get_session
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.chat_schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("", response_model=None, summary="Ask the nutrition assistant a question (Pro-gated)")
async def post_chat(
    request: ChatRequest,
    user_id: Annotated[uuid.UUID, Depends(get_authenticated_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[Container, Depends(get_container)],
) -> ChatResponse | JSONResponse:
    diary_history, nutrition_history, analytics_signals, entitlement_cache, chat_audit = (
        build_repositories(session)
    )
    handler = AnswerChatQueryHandler(
        entitlement_cache=entitlement_cache,
        entitlement_check=container.entitlement_check,
        diary_history=diary_history,
        nutrition_history=nutrition_history,
        analytics_signals=analytics_signals,
        vector_store=container.vector_store,
        embedding=container.embedding,
        conversation=container.conversation,
        chat_audit=chat_audit,
        knowledge_base_collection=container.settings.knowledge_base_collection,
    )

    chat_history = tuple(ChatMessage(role=m.role, content=m.content) for m in request.chat_history)

    try:
        result = await handler.handle(
            AnswerChatQueryCommand(user_id=user_id, query=request.query, chat_history=chat_history)
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)

    return ChatResponse(
        response=result.response_text,
        had_sufficient_context=result.had_sufficient_context,
        disclaimer_included=result.disclaimer_included,
        retrieved_record_count=len(result.retrieved_record_ids),
    )
