"""Pydantic v2 request/response models for POST /api/v1/chat
(api-conventions SKILL.md: "Pydantic v2 models for every request and
response -- never raw dicts")."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatMessageSchema(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    chat_history: list[ChatMessageSchema] = Field(default_factory=list)


class ChatResponse(BaseModel):
    response: str
    had_sufficient_context: bool
    disclaimer_included: bool
    retrieved_record_count: int
