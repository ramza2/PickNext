"""Auth HTTP routes."""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_email_sender
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import User
from app.schemas.auth import (
    AuthUserResponse,
    FindIdRequestCodeBody,
    FindIdVerifyBody,
    FindIdVerifyResponse,
    LoginBody,
    MessageResponse,
    PasswordResetConfirmBody,
    PasswordResetRequestCodeBody,
    SignupCompleteBody,
    SignupRequestCodeBody,
)
from app.services import auth_service, session_service
from app.services.auth_service import AuthError
from app.services.email import EmailSender

router = APIRouter(prefix="/auth", tags=["auth"])


def _raise_auth(exc: AuthError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    ) from exc


def _set_session_cookie(
    response: Response,
    *,
    raw_token: str,
    remember_me: bool,
    settings: Settings,
) -> None:
    kwargs: dict = {
        "key": settings.auth_cookie_name,
        "value": raw_token,
        "httponly": True,
        "secure": settings.auth_cookie_secure,
        "samesite": "lax",
        "path": "/",
    }
    if remember_me:
        kwargs["max_age"] = int(
            timedelta(days=settings.auth_remember_ttl_days).total_seconds()
        )
    response.set_cookie(**kwargs)


def _clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite="lax",
    )


@router.post("/signup/request-code", response_model=MessageResponse)
async def signup_request_code(
    body: SignupRequestCodeBody,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    email_sender: EmailSender = Depends(get_email_sender),
) -> MessageResponse:
    try:
        result = await auth_service.signup_request_code(
            db,
            login_id_raw=body.login_id,
            email_raw=body.email,
            settings=settings,
            email_sender=email_sender,
        )
    except AuthError as exc:
        _raise_auth(exc)
    return MessageResponse(**result)


@router.post("/signup/complete", response_model=AuthUserResponse, status_code=201)
async def signup_complete(
    body: SignupCompleteBody,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthUserResponse:
    try:
        user = await auth_service.signup_complete(
            db,
            login_id_raw=body.login_id,
            email_raw=body.email,
            verification_code=body.verification_code,
            password=body.password,
            password_confirm=body.password_confirm,
            settings=settings,
        )
    except AuthError as exc:
        _raise_auth(exc)
    return AuthUserResponse.model_validate(user)


@router.post("/login", response_model=AuthUserResponse)
def login(
    body: LoginBody,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthUserResponse:
    try:
        result = auth_service.login(
            db,
            login_id_raw=body.login_id,
            password=body.password,
            remember_me=body.remember_me,
            settings=settings,
        )
    except AuthError as exc:
        _raise_auth(exc)
    _set_session_cookie(
        response,
        raw_token=result.raw_token,
        remember_me=result.remember_me,
        settings=settings,
    )
    return AuthUserResponse.model_validate(result.user)


@router.get("/me", response_model=AuthUserResponse)
def me(user: User = Depends(get_current_user)) -> AuthUserResponse:
    return AuthUserResponse.model_validate(user)


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> MessageResponse:
    raw = request.cookies.get(settings.auth_cookie_name)
    if raw:
        session = session_service.get_active_session_for_token(db, raw_token=raw)
        if session is not None:
            session_service.revoke_session(db, session)
            db.commit()
    _clear_session_cookie(response, settings)
    return MessageResponse(message="로그아웃되었습니다.")


@router.post("/find-id/request-code", response_model=MessageResponse)
async def find_id_request_code(
    body: FindIdRequestCodeBody,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    email_sender: EmailSender = Depends(get_email_sender),
) -> MessageResponse:
    try:
        result = await auth_service.find_id_request_code(
            db,
            email_raw=body.email,
            settings=settings,
            email_sender=email_sender,
        )
    except AuthError as exc:
        _raise_auth(exc)
    return MessageResponse(**result)


@router.post("/find-id/verify", response_model=FindIdVerifyResponse)
def find_id_verify(
    body: FindIdVerifyBody,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FindIdVerifyResponse:
    try:
        result = auth_service.find_id_verify(
            db,
            email_raw=body.email,
            verification_code=body.verification_code,
            settings=settings,
        )
    except AuthError as exc:
        _raise_auth(exc)
    return FindIdVerifyResponse(**result)


@router.post("/password-reset/request-code", response_model=MessageResponse)
async def password_reset_request_code(
    body: PasswordResetRequestCodeBody,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    email_sender: EmailSender = Depends(get_email_sender),
) -> MessageResponse:
    try:
        result = await auth_service.password_reset_request_code(
            db,
            login_id_raw=body.login_id,
            email_raw=body.email,
            settings=settings,
            email_sender=email_sender,
        )
    except AuthError as exc:
        _raise_auth(exc)
    return MessageResponse(**result)


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def password_reset_confirm(
    body: PasswordResetConfirmBody,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    email_sender: EmailSender = Depends(get_email_sender),
) -> MessageResponse:
    try:
        await auth_service.password_reset_confirm(
            db,
            login_id_raw=body.login_id,
            email_raw=body.email,
            verification_code=body.verification_code,
            new_password=body.new_password,
            new_password_confirm=body.new_password_confirm,
            settings=settings,
            email_sender=email_sender,
        )
    except AuthError as exc:
        _raise_auth(exc)
    _clear_session_cookie(response, settings)
    return MessageResponse(message="비밀번호가 재설정되었습니다.")
