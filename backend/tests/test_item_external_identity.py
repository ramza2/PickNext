"""Item external identity constraints (requires Alembic 0005 schema)."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Category, CategoryType, Item, ItemStatus, User


def _category(db: Session, user: User) -> Category:
    cat = Category(
        user_id=user.id,
        name=f"cat-{uuid4().hex[:6]}",
        category_type=CategoryType.MEDIA,
        sort_order=1,
    )
    db.add(cat)
    db.flush()
    return cat


def test_legacy_null_external_identity_allowed(db: Session) -> None:
    user = User(
        email=f"ext-legacy-{uuid4().hex[:8]}@picknext.local",
        display_name="L",
        password_hash="h",
        is_active=True,
    )
    db.add(user)
    db.flush()
    cat = _category(db, user)
    for title in ("A", "B", "C"):
        db.add(
            Item(
                user_id=user.id,
                category_id=cat.id,
                title=title,
                status=ItemStatus.PLANNED,
                rating=Decimal("0.0"),
            )
        )
    db.flush()


def test_partial_external_identity_rejected(db: Session) -> None:
    user = User(
        email=f"ext-partial-{uuid4().hex[:8]}@picknext.local",
        display_name="P",
        password_hash="h",
        is_active=True,
    )
    db.add(user)
    db.flush()
    cat = _category(db, user)
    db.add(
        Item(
            user_id=user.id,
            category_id=cat.id,
            title="partial",
            status=ItemStatus.PLANNED,
            rating=Decimal("0.0"),
            external_source="tmdb",
            external_id=None,
            external_media_type=None,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_same_user_duplicate_tmdb_rejected(db: Session) -> None:
    user = User(
        email=f"ext-dup-{uuid4().hex[:8]}@picknext.local",
        display_name="D",
        password_hash="h",
        is_active=True,
    )
    db.add(user)
    db.flush()
    cat = _category(db, user)
    db.add(
        Item(
            user_id=user.id,
            category_id=cat.id,
            title="one",
            status=ItemStatus.PLANNED,
            rating=Decimal("0.0"),
            external_source="tmdb",
            external_id="872585",
            external_media_type="movie",
        )
    )
    db.flush()
    db.add(
        Item(
            user_id=user.id,
            category_id=cat.id,
            title="two",
            status=ItemStatus.PLANNED,
            rating=Decimal("0.0"),
            external_source="tmdb",
            external_id="872585",
            external_media_type="movie",
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_other_user_same_tmdb_allowed(db: Session) -> None:
    u1 = User(
        email=f"ext-u1-{uuid4().hex[:8]}@picknext.local",
        display_name="U1",
        password_hash="h",
        is_active=True,
    )
    u2 = User(
        email=f"ext-u2-{uuid4().hex[:8]}@picknext.local",
        display_name="U2",
        password_hash="h",
        is_active=True,
    )
    db.add_all([u1, u2])
    db.flush()
    c1 = _category(db, u1)
    c2 = _category(db, u2)
    db.add(
        Item(
            user_id=u1.id,
            category_id=c1.id,
            title="u1",
            status=ItemStatus.PLANNED,
            rating=Decimal("0.0"),
            external_source="tmdb",
            external_id="872585",
            external_media_type="movie",
        )
    )
    db.add(
        Item(
            user_id=u2.id,
            category_id=c2.id,
            title="u2",
            status=ItemStatus.PLANNED,
            rating=Decimal("0.0"),
            external_source="tmdb",
            external_id="872585",
            external_media_type="movie",
        )
    )
    db.flush()


def test_movie_and_tv_same_numeric_id_allowed(db: Session) -> None:
    user = User(
        email=f"ext-mt-{uuid4().hex[:8]}@picknext.local",
        display_name="MT",
        password_hash="h",
        is_active=True,
    )
    db.add(user)
    db.flush()
    cat = _category(db, user)
    db.add(
        Item(
            user_id=user.id,
            category_id=cat.id,
            title="movie",
            status=ItemStatus.PLANNED,
            rating=Decimal("0.0"),
            external_source="tmdb",
            external_id="100",
            external_media_type="movie",
        )
    )
    db.add(
        Item(
            user_id=user.id,
            category_id=cat.id,
            title="tv",
            status=ItemStatus.PLANNED,
            rating=Decimal("0.0"),
            external_source="tmdb",
            external_id="100",
            external_media_type="tv",
        )
    )
    db.flush()


def test_item_model_has_external_identity_metadata() -> None:
    cols = set(Item.__table__.c.keys())
    for name in (
        "external_source",
        "external_id",
        "external_media_type",
        "original_title",
        "original_language",
        "poster_path",
        "backdrop_path",
        "external_metadata_updated_at",
    ):
        assert name in cols
    index_names = {index.name for index in Item.__table__.indexes}
    assert "uq_items_user_external_identity" in index_names
