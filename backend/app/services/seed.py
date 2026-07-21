"""Idempotent development seed data."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Category, CategoryType, User

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CategorySeed:
    name: str
    category_type: CategoryType
    sort_order: int


DEFAULT_CATEGORIES: tuple[CategorySeed, ...] = (
    CategorySeed("애니메이션", CategoryType.MEDIA, 1),
    CategorySeed("애니 영화", CategoryType.MEDIA, 2),
    CategorySeed("영화", CategoryType.MEDIA, 3),
    CategorySeed("한국드라마", CategoryType.MEDIA, 4),
    CategorySeed("일본드라마", CategoryType.MEDIA, 5),
    CategorySeed("중국드라마", CategoryType.MEDIA, 6),
    CategorySeed("미국드라마", CategoryType.MEDIA, 7),
    CategorySeed("예능", CategoryType.MEDIA, 8),
    CategorySeed("만화책", CategoryType.BOOK, 9),
    CategorySeed("음식", CategoryType.FOOD, 10),
)


def hash_password(password: str) -> str:
    """Placeholder hash for seed user until auth is implemented."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def get_or_create_seed_user(db: Session) -> User:
    settings = get_settings()
    user = db.scalar(select(User).where(User.email == settings.seed_user_email))
    if user is not None:
        return user

    user = User(
        email=settings.seed_user_email,
        display_name=settings.seed_user_display_name,
        password_hash=hash_password(settings.seed_user_password),
        is_active=True,
    )
    db.add(user)
    db.flush()
    logger.info("Created seed user: %s", user.email)
    return user


def seed_categories(db: Session, user: User) -> tuple[int, int]:
    """Return (created_count, existing_count)."""
    created = 0
    existing = 0
    for seed in DEFAULT_CATEGORIES:
        category = db.scalar(
            select(Category).where(
                Category.user_id == user.id,
                Category.name == seed.name,
            )
        )
        if category is not None:
            existing += 1
            # Keep sort_order / type aligned with seed definition.
            category.category_type = seed.category_type
            category.sort_order = seed.sort_order
            continue

        db.add(
            Category(
                user_id=user.id,
                name=seed.name,
                category_type=seed.category_type,
                sort_order=seed.sort_order,
            )
        )
        created += 1
    return created, existing


def run_seed(db: Session | None = None) -> dict[str, int | str]:
    owns_session = db is None
    session = db or SessionLocal()
    try:
        user = get_or_create_seed_user(session)
        created, existing = seed_categories(session, user)
        if owns_session:
            session.commit()
        else:
            session.flush()
        result = {
            "user_email": user.email,
            "categories_created": created,
            "categories_existing": existing,
            "categories_total": created + existing,
        }
        logger.info("Seed completed: %s", result)
        return result
    except Exception:
        if owns_session:
            session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    result = run_seed()
    print(result)


if __name__ == "__main__":
    main()
