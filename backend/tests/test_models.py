from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Category,
    CategoryType,
    Collection,
    Item,
    ItemStatus,
    User,
)
from app.schemas import ItemCreate


def test_model_creation(db: Session, user: User):
    category = Category(
        user_id=user.id,
        name="영화",
        category_type=CategoryType.MEDIA,
        sort_order=1,
    )
    collection = Collection(user_id=user.id, name="터미네이터")
    db.add_all([category, collection])
    db.flush()

    item = Item(
        user_id=user.id,
        category_id=category.id,
        collection_id=collection.id,
        title="터미네이터 2",
        status=ItemStatus.PLANNED,
        rating=Decimal("4.5"),
        progress_note="1회 시청",
        memo="액션",
    )
    db.add(item)
    db.flush()

    assert item.id is not None
    assert item.collection_id == collection.id
    assert item.deleted_at is None


def test_rating_range_orm_validation(db: Session, user: User):
    category = Category(
        user_id=user.id,
        name="테스트카테고리",
        category_type=CategoryType.GENERAL,
        sort_order=1,
    )
    db.add(category)
    db.flush()

    with pytest.raises(ValueError, match="rating must be between"):
        Item(
            user_id=user.id,
            category_id=category.id,
            title="과한 평점",
            status=ItemStatus.PLANNED,
            rating=Decimal("5.5"),
        )


def test_rating_half_step_schema_validation():
    with pytest.raises(ValidationError):
        ItemCreate(
            category_id="00000000-0000-0000-0000-000000000001",
            title="잘못된 평점",
            status=ItemStatus.PLANNED,
            rating=Decimal("4.3"),
        )


def test_required_fields_schema_validation():
    with pytest.raises(ValidationError):
        ItemCreate(
            category_id="00000000-0000-0000-0000-000000000001",
            title="",
            status=ItemStatus.PLANNED,
            rating=Decimal("3.0"),
        )


def test_unique_user_email(db: Session, user: User):
    db.add(
        User(
            email=user.email,
            display_name="Dup",
            password_hash="hash2",
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_unique_category_name_per_user(db: Session, user: User):
    db.add(
        Category(
            user_id=user.id,
            name="영화",
            category_type=CategoryType.MEDIA,
            sort_order=1,
        )
    )
    db.flush()
    db.add(
        Category(
            user_id=user.id,
            name="영화",
            category_type=CategoryType.MEDIA,
            sort_order=2,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_unique_collection_name_per_user(db: Session, user: User):
    db.add(Collection(user_id=user.id, name="터미네이터"))
    db.flush()
    db.add(Collection(user_id=user.id, name="터미네이터"))
    with pytest.raises(IntegrityError):
        db.flush()
