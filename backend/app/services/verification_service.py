"""Email verification code lifecycle."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import (
    constant_time_equals,
    generate_verification_code,
    hash_verification_code,
)
from app.models import AuthVerificationCode


class VerificationPurpose(StrEnum):
    SIGNUP = "SIGNUP"
    FIND_LOGIN_ID = "FIND_LOGIN_ID"
    RESET_PASSWORD = "RESET_PASSWORD"


class VerificationErrorCode(StrEnum):
    INVALID = "AUTH_CODE_INVALID"
    EXPIRED = "AUTH_CODE_EXPIRED"
    ATTEMPTS_EXCEEDED = "AUTH_CODE_ATTEMPTS_EXCEEDED"
    RESEND_TOO_SOON = "AUTH_CODE_RESEND_TOO_SOON"


class VerificationError(Exception):
    def __init__(self, code: VerificationErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _pepper(settings: Settings) -> str:
    return settings.auth_code_pepper.get_secret_value()


def invalidate_active_codes(
    db: Session,
    *,
    purpose: VerificationPurpose,
    email: str,
    login_id: str | None = None,
) -> None:
    now = _utcnow()
    stmt = (
        update(AuthVerificationCode)
        .where(
            AuthVerificationCode.purpose == purpose.value,
            AuthVerificationCode.email == email,
            AuthVerificationCode.consumed_at.is_(None),
            AuthVerificationCode.invalidated_at.is_(None),
        )
        .values(invalidated_at=now)
    )
    if login_id is not None:
        stmt = stmt.where(AuthVerificationCode.login_id == login_id)
    db.execute(stmt)
    db.flush()


def assert_resend_allowed(
    db: Session,
    *,
    purpose: VerificationPurpose,
    email: str,
    settings: Settings,
    login_id: str | None = None,
) -> None:
    stmt = (
        select(AuthVerificationCode)
        .where(
            AuthVerificationCode.purpose == purpose.value,
            AuthVerificationCode.email == email,
        )
        .order_by(AuthVerificationCode.created_at.desc())
        .limit(1)
    )
    if login_id is not None:
        stmt = stmt.where(AuthVerificationCode.login_id == login_id)
    latest = db.scalar(stmt)
    if latest is None:
        return
    wait = timedelta(seconds=settings.auth_code_resend_seconds)
    if _utcnow() - latest.created_at < wait:
        raise VerificationError(
            VerificationErrorCode.RESEND_TOO_SOON,
            "인증번호를 너무 자주 요청했습니다. 잠시 후 다시 시도하세요.",
        )


def create_code(
    db: Session,
    *,
    purpose: VerificationPurpose,
    email: str,
    settings: Settings,
    login_id: str | None = None,
    user_id: UUID | None = None,
) -> tuple[AuthVerificationCode, str]:
    """Create a code row and return (row, plaintext_code). Caller must send email."""
    assert_resend_allowed(
        db,
        purpose=purpose,
        email=email,
        settings=settings,
        login_id=login_id,
    )
    invalidate_active_codes(db, purpose=purpose, email=email, login_id=login_id)

    raw_code = generate_verification_code()
    now = _utcnow()
    row = AuthVerificationCode(
        purpose=purpose.value,
        email=email,
        login_id=login_id,
        user_id=user_id,
        code_hash=hash_verification_code(
            pepper=_pepper(settings),
            purpose=purpose.value,
            email=email,
            code=raw_code,
        ),
        attempt_count=0,
        expires_at=now + timedelta(minutes=settings.auth_code_ttl_minutes),
        consumed_at=None,
        invalidated_at=None,
    )
    db.add(row)
    db.flush()
    return row, raw_code


def invalidate_code(db: Session, row: AuthVerificationCode) -> None:
    if row.invalidated_at is None:
        row.invalidated_at = _utcnow()
        db.flush()


def verify_code(
    db: Session,
    *,
    purpose: VerificationPurpose,
    email: str,
    code: str,
    settings: Settings,
    login_id: str | None = None,
    consume: bool = True,
) -> AuthVerificationCode:
    stmt = (
        select(AuthVerificationCode)
        .where(
            AuthVerificationCode.purpose == purpose.value,
            AuthVerificationCode.email == email,
            AuthVerificationCode.consumed_at.is_(None),
            AuthVerificationCode.invalidated_at.is_(None),
        )
        .order_by(AuthVerificationCode.created_at.desc())
        .limit(1)
    )
    if login_id is not None:
        stmt = stmt.where(AuthVerificationCode.login_id == login_id)

    row = db.scalar(stmt)
    if row is None:
        raise VerificationError(
            VerificationErrorCode.INVALID,
            "인증번호가 올바르지 않습니다.",
        )

    now = _utcnow()
    if row.expires_at <= now:
        invalidate_code(db, row)
        raise VerificationError(
            VerificationErrorCode.EXPIRED,
            "인증번호가 만료되었습니다.",
        )

    if row.attempt_count >= settings.auth_code_max_attempts:
        invalidate_code(db, row)
        raise VerificationError(
            VerificationErrorCode.ATTEMPTS_EXCEEDED,
            "인증번호 시도 횟수를 초과했습니다.",
        )

    expected = hash_verification_code(
        pepper=_pepper(settings),
        purpose=purpose.value,
        email=email,
        code=code.strip(),
    )
    if not constant_time_equals(row.code_hash, expected):
        row.attempt_count += 1
        db.flush()
        if row.attempt_count >= settings.auth_code_max_attempts:
            invalidate_code(db, row)
            raise VerificationError(
                VerificationErrorCode.ATTEMPTS_EXCEEDED,
                "인증번호 시도 횟수를 초과했습니다.",
            )
        raise VerificationError(
            VerificationErrorCode.INVALID,
            "인증번호가 올바르지 않습니다.",
        )

    if consume:
        row.consumed_at = now
        db.flush()
    return row
