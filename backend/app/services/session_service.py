"""User session create / lookup / revoke."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import generate_session_token, hash_session_token
from app.models import User, UserSession

LAST_SEEN_THROTTLE = timedelta(minutes=10)
CLEANUP_BATCH_LIMIT = 50


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_session(
    db: Session,
    *,
    user: User,
    remember_me: bool,
    settings: Settings,
) -> tuple[UserSession, str]:
    now = _utcnow()
    if remember_me:
        expires_at = now + timedelta(days=settings.auth_remember_ttl_days)
    else:
        expires_at = now + timedelta(hours=settings.auth_session_ttl_hours)

    raw_token = generate_session_token()
    session = UserSession(
        user_id=user.id,
        token_hash=hash_session_token(raw_token),
        is_persistent=remember_me,
        expires_at=expires_at,
        last_seen_at=now,
        revoked_at=None,
    )
    db.add(session)
    db.flush()
    return session, raw_token


def get_active_session_for_token(
    db: Session,
    *,
    raw_token: str,
) -> UserSession | None:
    token_hash = hash_session_token(raw_token)
    session = db.scalar(
        select(UserSession).where(UserSession.token_hash == token_hash)
    )
    if session is None:
        return None
    now = _utcnow()
    if session.revoked_at is not None:
        return None
    if session.expires_at <= now:
        if session.revoked_at is None:
            session.revoked_at = now
            db.flush()
        return None
    return session


def touch_session_last_seen(db: Session, session: UserSession) -> None:
    now = _utcnow()
    if now - session.last_seen_at >= LAST_SEEN_THROTTLE:
        session.last_seen_at = now
        db.flush()


def revoke_session(db: Session, session: UserSession) -> None:
    if session.revoked_at is None:
        session.revoked_at = _utcnow()
        db.flush()


def revoke_all_sessions_for_user(db: Session, user_id: UUID) -> int:
    now = _utcnow()
    result = db.execute(
        update(UserSession)
        .where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    db.flush()
    return int(result.rowcount or 0)


def opportunistic_cleanup(db: Session) -> int:
    """Revoke a small batch of expired sessions that are still unmarked."""
    now = _utcnow()
    expired_ids = list(
        db.scalars(
            select(UserSession.id)
            .where(
                UserSession.revoked_at.is_(None),
                UserSession.expires_at <= now,
            )
            .limit(CLEANUP_BATCH_LIMIT)
        ).all()
    )
    if not expired_ids:
        return 0
    result = db.execute(
        update(UserSession)
        .where(UserSession.id.in_(expired_ids))
        .values(revoked_at=now)
    )
    db.flush()
    return int(result.rowcount or 0)
