"""Pydantic v2 request/response models for /api/v1/auth (api-conventions
SKILL.md). Never include password_hash or a raw token outside its one
intended field."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field


class ErrorResponse(BaseModel):
    error: str
    code: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RegisterResponse(BaseModel):
    user_id: uuid.UUID


class VerifyEmailRequest(BaseModel):
    reference_id: str
    secret: str


class VerifyEmailResponse(BaseModel):
    user_id: uuid.UUID


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LogoutRequest(BaseModel):
    refresh_token: str


class LogoutResponse(BaseModel):
    revoked: bool


class PasswordResetRequestRequest(BaseModel):
    email: EmailStr


class PasswordResetRequestResponse(BaseModel):
    detail: str = "If an account exists for this email, a reset link has been sent."


class PasswordResetConfirmRequest(BaseModel):
    reference_id: str
    secret: str
    new_password: str = Field(min_length=1)


class PasswordResetConfirmResponse(BaseModel):
    user_id: uuid.UUID
