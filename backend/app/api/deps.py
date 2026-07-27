"""Shared API dependencies."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import User
from app.services import session_service
from app.services.email import EmailSender, SmtpEmailSender

_email_sender_override: EmailSender | None = None


def set_email_sender_override(sender: EmailSender | None) -> None:
    global _email_sender_override
    _email_sender_override = sender


def get_email_sender(settings: Settings = Depends(get_settings)) -> EmailSender:
    if _email_sender_override is not None:
        return _email_sender_override
    return SmtpEmailSender(settings)


def auth_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """Resolve the active user from the HttpOnly session cookie."""
    raw = request.cookies.get(settings.auth_cookie_name)
    if not raw:
        raise auth_error(
            status.HTTP_401_UNAUTHORIZED,
            "AUTH_REQUIRED",
            "로그인이 필요합니다.",
        )

    session = session_service.get_active_session_for_token(db, raw_token=raw)
    if session is None:
        raise auth_error(
            status.HTTP_401_UNAUTHORIZED,
            "AUTH_SESSION_EXPIRED",
            "세션이 만료되었습니다. 다시 로그인해 주세요.",
        )

    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        session_service.revoke_session(db, session)
        db.commit()
        raise auth_error(
            status.HTTP_401_UNAUTHORIZED,
            "AUTH_REQUIRED",
            "로그인이 필요합니다.",
        )

    session_service.touch_session_last_seen(db, session)
    db.commit()
    return user
