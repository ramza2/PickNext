"""Auth migration schema and ORM round-trip tests (AUTH-1)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_session_token, hash_verification_code
from app.models import AuthVerificationCode, User, UserSession
from app.services.verification_service import VerificationPurpose


def test_auth_tables_exist(engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert "user_sessions" in tables
    assert "auth_verification_codes" in tables


def test_users_auth_columns_exist(engine) -> None:
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("users")}
    assert "login_id" in columns
    assert "email_verified_at" in columns
    assert "last_login_at" in columns


def test_auth_verification_code_orm_round_trip(db: Session) -> None:
    settings = get_settings()
    email = f"migration-{uuid4().hex[:8]}@example.com"
    now = datetime.now(timezone.utc)

    row = AuthVerificationCode(
        purpose=VerificationPurpose.SIGNUP.value,
        email=email,
        login_id=f"mig{uuid4().hex[:6]}",
        code_hash=hash_verification_code(
            pepper=settings.auth_code_pepper.get_secret_value(),
            purpose=VerificationPurpose.SIGNUP.value,
            email=email,
            code="123456",
        ),
        attempt_count=0,
        expires_at=now + timedelta(minutes=10),
    )
    db.add(row)
    db.flush()

    loaded = db.get(AuthVerificationCode, row.id)
    assert loaded is not None
    assert loaded.purpose == VerificationPurpose.SIGNUP.value
    assert loaded.email == email
    assert loaded.consumed_at is None
    assert loaded.invalidated_at is None


def test_user_session_orm_round_trip(db: Session, user: User) -> None:
    now = datetime.now(timezone.utc)
    raw_token = f"test-session-token-{uuid4().hex}"

    session = UserSession(
        user_id=user.id,
        token_hash=hash_session_token(raw_token),
        is_persistent=False,
        expires_at=now + timedelta(hours=12),
        last_seen_at=now,
    )
    db.add(session)
    db.flush()

    loaded = db.scalar(select(UserSession).where(UserSession.id == session.id))
    assert loaded is not None
    assert loaded.user_id == user.id
    assert loaded.revoked_at is None
    assert loaded.token_hash == hash_session_token(raw_token)


def test_user_session_relationship(db: Session, user: User) -> None:
    now = datetime.now(timezone.utc)
    session = UserSession(
        user_id=user.id,
        token_hash=hash_session_token(f"rel-{uuid4().hex}"),
        is_persistent=True,
        expires_at=now + timedelta(days=30),
        last_seen_at=now,
    )
    db.add(session)
    db.flush()

    db.refresh(user)
    assert any(s.id == session.id for s in user.sessions)
