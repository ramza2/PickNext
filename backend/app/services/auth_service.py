"""Auth business logic: signup, login, find-id, password reset."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import (
    LOGIN_ID_PATTERN,
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    hash_password,
    normalize_email,
    normalize_login_id,
    run_dummy_password_verify,
    verify_password,
)
from app.models import User
from app.services.email import (
    EmailSendError,
    EmailSender,
    OutgoingEmail,
    build_password_changed_email,
    build_verification_email,
)
from app.services.seed import ensure_default_categories_for_user
from app.services import session_service
from app.services.verification_service import (
    VerificationError,
    VerificationPurpose,
    create_code,
    invalidate_code,
    verify_code,
)

logger = logging.getLogger(__name__)

_LOGIN_ID_RE = re.compile(LOGIN_ID_PATTERN)


class AuthError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class LoginResult:
    user: User
    raw_token: str
    remember_me: bool


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def validate_login_id_value(raw: str) -> str:
    login_id = normalize_login_id(raw)
    if not _LOGIN_ID_RE.fullmatch(login_id):
        raise AuthError(
            "AUTH_INVALID_LOGIN_ID",
            "아이디 형식이 올바르지 않습니다.",
            status_code=422,
        )
    return login_id


def validate_email_value(raw: str) -> str:
    email = normalize_email(raw)
    try:
        result = validate_email(email, check_deliverability=False)
    except EmailNotValidError as exc:
        raise AuthError(
            "AUTH_INVALID_EMAIL",
            "이메일 형식이 올바르지 않습니다.",
            status_code=422,
        ) from exc
    return result.normalized


def validate_password_value(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError(
            "AUTH_INVALID_PASSWORD",
            f"비밀번호는 {MIN_PASSWORD_LENGTH}자 이상이어야 합니다.",
            status_code=422,
        )
    if len(password) > MAX_PASSWORD_LENGTH:
        raise AuthError(
            "AUTH_INVALID_PASSWORD",
            f"비밀번호는 {MAX_PASSWORD_LENGTH}자 이하여야 합니다.",
            status_code=422,
        )
    return password


def _get_user_by_login_id(db: Session, login_id: str) -> User | None:
    return db.scalar(select(User).where(User.login_id == login_id))


def _get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


async def _send_code_email(
    *,
    db: Session,
    sender: EmailSender,
    row,
    to_email: str,
    purpose_label: str,
    raw_code: str,
    settings: Settings,
) -> None:
    subject, body = build_verification_email(
        purpose_label=purpose_label,
        code=raw_code,
        ttl_minutes=settings.auth_code_ttl_minutes,
    )
    try:
        await sender.send(
            OutgoingEmail(to_email=to_email, subject=subject, body_text=body)
        )
    except EmailSendError:
        db.refresh(row)
        invalidate_code(db, row)
        db.commit()
        logger.warning("Auth verification email unavailable purpose=%s", purpose_label)
        raise AuthError(
            "AUTH_EMAIL_UNAVAILABLE",
            "인증 메일을 보낼 수 없습니다. 잠시 후 다시 시도하세요.",
            status_code=503,
        ) from None


async def signup_request_code(
    db: Session,
    *,
    login_id_raw: str,
    email_raw: str,
    settings: Settings,
    email_sender: EmailSender,
) -> dict[str, str]:
    login_id = validate_login_id_value(login_id_raw)
    email = validate_email_value(email_raw)

    if _get_user_by_login_id(db, login_id) is not None:
        raise AuthError("AUTH_LOGIN_ID_TAKEN", "이미 사용 중인 아이디입니다.")
    if _get_user_by_email(db, email) is not None:
        raise AuthError("AUTH_EMAIL_TAKEN", "이미 가입된 이메일입니다.")

    try:
        row, raw_code = create_code(
            db,
            purpose=VerificationPurpose.SIGNUP,
            email=email,
            login_id=login_id,
            settings=settings,
        )
    except VerificationError as exc:
        raise AuthError(exc.code.value, exc.message, status_code=429) from exc

    db.commit()
    await _send_code_email(
        db=db,
        sender=email_sender,
        row=row,
        to_email=email,
        purpose_label="회원가입 인증번호",
        raw_code=raw_code,
        settings=settings,
    )
    db.commit()
    return {"message": "입력한 이메일로 인증 안내를 전송했습니다."}


async def signup_complete(
    db: Session,
    *,
    login_id_raw: str,
    email_raw: str,
    verification_code: str,
    password: str,
    password_confirm: str,
    settings: Settings,
) -> User:
    login_id = validate_login_id_value(login_id_raw)
    email = validate_email_value(email_raw)
    validate_password_value(password)
    if password != password_confirm:
        raise AuthError(
            "AUTH_PASSWORD_MISMATCH",
            "비밀번호 확인이 일치하지 않습니다.",
            status_code=422,
        )

    try:
        verify_code(
            db,
            purpose=VerificationPurpose.SIGNUP,
            email=email,
            login_id=login_id,
            code=verification_code,
            settings=settings,
            consume=True,
        )
    except VerificationError as exc:
        status = 429 if exc.code.value.endswith("TOO_SOON") or "ATTEMPTS" in exc.code.value else 400
        if exc.code.value == "AUTH_CODE_EXPIRED":
            status = 400
        raise AuthError(exc.code.value, exc.message, status_code=status) from exc

    if _get_user_by_login_id(db, login_id) is not None:
        raise AuthError("AUTH_LOGIN_ID_TAKEN", "이미 사용 중인 아이디입니다.")
    if _get_user_by_email(db, email) is not None:
        raise AuthError("AUTH_EMAIL_TAKEN", "이미 가입된 이메일입니다.")

    now = _utcnow()
    user = User(
        email=email,
        display_name=login_id,
        login_id=login_id,
        password_hash=hash_password(password),
        is_active=True,
        email_verified_at=now,
        last_login_at=None,
    )
    db.add(user)
    db.flush()
    ensure_default_categories_for_user(db, user)
    db.commit()
    db.refresh(user)
    return user


def login(
    db: Session,
    *,
    login_id_raw: str,
    password: str,
    remember_me: bool,
    settings: Settings,
) -> LoginResult:
    login_id = normalize_login_id(login_id_raw)
    user = _get_user_by_login_id(db, login_id) if login_id else None

    if user is None:
        run_dummy_password_verify(password)
        raise AuthError(
            "AUTH_INVALID_CREDENTIALS",
            "아이디 또는 비밀번호가 올바르지 않습니다.",
            status_code=401,
        )

    if not user.is_active or not verify_password(password, user.password_hash):
        raise AuthError(
            "AUTH_INVALID_CREDENTIALS",
            "아이디 또는 비밀번호가 올바르지 않습니다.",
            status_code=401,
        )

    session_service.opportunistic_cleanup(db)
    _session, raw_token = session_service.create_session(
        db, user=user, remember_me=remember_me, settings=settings
    )
    user.last_login_at = _utcnow()
    db.commit()
    db.refresh(user)
    return LoginResult(user=user, raw_token=raw_token, remember_me=remember_me)


async def find_id_request_code(
    db: Session,
    *,
    email_raw: str,
    settings: Settings,
    email_sender: EmailSender,
) -> dict[str, str]:
    generic = {"message": "입력한 이메일로 인증 안내를 전송했습니다."}
    try:
        email = validate_email_value(email_raw)
    except AuthError:
        return generic

    user = _get_user_by_email(db, email)
    if user is None or not user.login_id:
        return generic

    try:
        row, raw_code = create_code(
            db,
            purpose=VerificationPurpose.FIND_LOGIN_ID,
            email=email,
            user_id=user.id,
            settings=settings,
        )
    except VerificationError as exc:
        raise AuthError(exc.code.value, exc.message, status_code=429) from exc

    db.commit()
    await _send_code_email(
        db=db,
        sender=email_sender,
        row=row,
        to_email=email,
        purpose_label="아이디 찾기 인증번호",
        raw_code=raw_code,
        settings=settings,
    )
    db.commit()
    return generic


def find_id_verify(
    db: Session,
    *,
    email_raw: str,
    verification_code: str,
    settings: Settings,
) -> dict[str, str]:
    email = validate_email_value(email_raw)
    try:
        verify_code(
            db,
            purpose=VerificationPurpose.FIND_LOGIN_ID,
            email=email,
            code=verification_code,
            settings=settings,
            consume=True,
        )
    except VerificationError as exc:
        status = 400
        if exc.code.value == "AUTH_CODE_ATTEMPTS_EXCEEDED":
            status = 429
        raise AuthError(exc.code.value, exc.message, status_code=status) from exc

    user = _get_user_by_email(db, email)
    if user is None or not user.login_id:
        raise AuthError(
            "AUTH_CODE_INVALID",
            "인증번호가 올바르지 않습니다.",
            status_code=400,
        )
    db.commit()
    return {"login_id": user.login_id}


async def password_reset_request_code(
    db: Session,
    *,
    login_id_raw: str,
    email_raw: str,
    settings: Settings,
    email_sender: EmailSender,
) -> dict[str, str]:
    generic = {"message": "입력한 이메일로 인증 안내를 전송했습니다."}
    try:
        login_id = validate_login_id_value(login_id_raw)
        email = validate_email_value(email_raw)
    except AuthError:
        return generic

    user = _get_user_by_login_id(db, login_id)
    if user is None or user.email != email:
        return generic

    try:
        row, raw_code = create_code(
            db,
            purpose=VerificationPurpose.RESET_PASSWORD,
            email=email,
            login_id=login_id,
            user_id=user.id,
            settings=settings,
        )
    except VerificationError as exc:
        raise AuthError(exc.code.value, exc.message, status_code=429) from exc

    db.commit()
    await _send_code_email(
        db=db,
        sender=email_sender,
        row=row,
        to_email=email,
        purpose_label="비밀번호 재설정 인증번호",
        raw_code=raw_code,
        settings=settings,
    )
    db.commit()
    return generic


async def password_reset_confirm(
    db: Session,
    *,
    login_id_raw: str,
    email_raw: str,
    verification_code: str,
    new_password: str,
    new_password_confirm: str,
    settings: Settings,
    email_sender: EmailSender,
) -> None:
    login_id = validate_login_id_value(login_id_raw)
    email = validate_email_value(email_raw)
    validate_password_value(new_password)
    if new_password != new_password_confirm:
        raise AuthError(
            "AUTH_PASSWORD_MISMATCH",
            "비밀번호 확인이 일치하지 않습니다.",
            status_code=422,
        )

    try:
        verify_code(
            db,
            purpose=VerificationPurpose.RESET_PASSWORD,
            email=email,
            login_id=login_id,
            code=verification_code,
            settings=settings,
            consume=True,
        )
    except VerificationError as exc:
        status = 429 if "ATTEMPTS" in exc.code.value else 400
        raise AuthError(exc.code.value, exc.message, status_code=status) from exc

    user = _get_user_by_login_id(db, login_id)
    if user is None or user.email != email:
        raise AuthError(
            "AUTH_CODE_INVALID",
            "인증번호가 올바르지 않습니다.",
            status_code=400,
        )

    user.password_hash = hash_password(new_password)
    session_service.revoke_all_sessions_for_user(db, user.id)
    db.commit()

    subject, body = build_password_changed_email()
    try:
        await email_sender.send(
            OutgoingEmail(to_email=email, subject=subject, body_text=body)
        )
    except EmailSendError:
        logger.warning(
            "Password-changed notification email failed user_id=%s",
            user.id,
        )
