"""Shared API dependencies."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import User


def get_current_user(db: Session = Depends(get_db)) -> User:
    """Resolve the active user from SEED_USER_EMAIL until auth is added."""
    settings = get_settings()
    user = db.scalar(select(User).where(User.email == settings.seed_user_email))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Seed user is not configured. Run seed and check SEED_USER_EMAIL.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Seed user is inactive.",
        )
    return user
