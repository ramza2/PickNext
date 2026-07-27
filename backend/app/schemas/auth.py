"""Auth request/response schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuthUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    login_id: str | None
    email: str


class MessageResponse(BaseModel):
    message: str


class SignupRequestCodeBody(BaseModel):
    login_id: str = Field(min_length=1, max_length=30)
    email: str = Field(min_length=3, max_length=320)


class SignupCompleteBody(BaseModel):
    login_id: str = Field(min_length=1, max_length=30)
    email: str = Field(min_length=3, max_length=320)
    verification_code: str = Field(min_length=6, max_length=6)
    password: str = Field(min_length=1, max_length=128)
    password_confirm: str = Field(min_length=1, max_length=128)


class LoginBody(BaseModel):
    login_id: str = Field(min_length=1, max_length=30)
    password: str = Field(min_length=1, max_length=128)
    remember_me: bool = False


class FindIdRequestCodeBody(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class FindIdVerifyBody(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    verification_code: str = Field(min_length=6, max_length=6)


class FindIdVerifyResponse(BaseModel):
    login_id: str


class PasswordResetRequestCodeBody(BaseModel):
    login_id: str = Field(min_length=1, max_length=30)
    email: str = Field(min_length=3, max_length=320)


class PasswordResetConfirmBody(BaseModel):
    login_id: str = Field(min_length=1, max_length=30)
    email: str = Field(min_length=3, max_length=320)
    verification_code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=1, max_length=128)
    new_password_confirm: str = Field(min_length=1, max_length=128)
