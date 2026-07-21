from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Category, User
from app.services.seed import DEFAULT_CATEGORIES, run_seed


def test_seed_categories_idempotent(db: Session, monkeypatch):
    monkeypatch.setenv("SEED_USER_EMAIL", "seed-idempotent@picknext.local")
    monkeypatch.setenv("SEED_USER_DISPLAY_NAME", "Seed Idempotent User")
    get_settings.cache_clear()

    first = run_seed(db)
    assert first["categories_created"] == len(DEFAULT_CATEGORIES)
    assert first["categories_total"] == len(DEFAULT_CATEGORIES)

    second = run_seed(db)
    assert second["categories_created"] == 0
    assert second["categories_existing"] == len(DEFAULT_CATEGORIES)
    assert second["categories_total"] == len(DEFAULT_CATEGORIES)

    user = db.scalar(select(User).where(User.email == first["user_email"]))
    assert user is not None

    count = db.scalar(
        select(func.count()).select_from(Category).where(Category.user_id == user.id)
    )
    assert count == len(DEFAULT_CATEGORIES)

    names = set(
        db.scalars(select(Category.name).where(Category.user_id == user.id)).all()
    )
    assert names == {seed.name for seed in DEFAULT_CATEGORIES}

    get_settings.cache_clear()
