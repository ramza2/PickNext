"""COL-1: POST /collections/{id}/items bulk attach for unassigned items."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.main import create_app
from app.models import (
    Category,
    CategoryType,
    Collection,
    Item,
    ItemStatus,
    User,
)


@pytest.fixture
def owner(db: Session) -> User:
    user = User(
        email=f"col-add-owner-{uuid4().hex[:8]}@picknext.local",
        display_name="Owner",
        password_hash="hash",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def other_user(db: Session) -> User:
    user = User(
        email=f"col-add-other-{uuid4().hex[:8]}@picknext.local",
        display_name="Other",
        password_hash="hash",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def api_client(db: Session, owner: User) -> TestClient:
    app = create_app()

    def _override_db():
        yield db

    def _override_user():
        return owner

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _category(db: Session, user: User, name: str = "영화") -> Category:
    cat = Category(
        user_id=user.id,
        name=name,
        category_type=CategoryType.MEDIA,
        sort_order=1,
    )
    db.add(cat)
    db.flush()
    return cat


def _collection(db: Session, user: User, name: str) -> Collection:
    col = Collection(user_id=user.id, name=name)
    db.add(col)
    db.flush()
    return col


def _item(
    db: Session,
    *,
    user: User,
    category: Category,
    title: str,
    collection: Collection | None = None,
    status: ItemStatus = ItemStatus.PLANNED,
) -> Item:
    item = Item(
        user_id=user.id,
        category_id=category.id,
        collection_id=collection.id if collection else None,
        title=title,
        status=status,
        rating=Decimal("0.0"),
    )
    db.add(item)
    db.flush()
    return item


def test_add_single_unassigned_item(
    api_client: TestClient,
    db: Session,
    owner: User,
) -> None:
    cat = _category(db, owner)
    col = _collection(db, owner, "타겟")
    item = _item(db, user=owner, category=cat, title="미지정 1")

    response = api_client.post(
        f"/api/v1/collections/{col.id}/items",
        json={"item_ids": [str(item.id)]},
    )
    assert response.status_code == 200
    assert response.json()["added_count"] == 1
    db.refresh(item)
    assert item.collection_id == col.id


def test_add_multiple_unassigned_items(
    api_client: TestClient,
    db: Session,
    owner: User,
) -> None:
    cat = _category(db, owner)
    col = _collection(db, owner, "타겟 멀티")
    items = [
        _item(db, user=owner, category=cat, title=f"미지정 {i}")
        for i in range(3)
    ]

    response = api_client.post(
        f"/api/v1/collections/{col.id}/items",
        json={"item_ids": [str(item.id) for item in items]},
    )
    assert response.status_code == 200
    assert response.json()["added_count"] == 3
    for item in items:
        db.refresh(item)
        assert item.collection_id == col.id


def test_add_items_idempotent_when_already_in_target(
    api_client: TestClient,
    db: Session,
    owner: User,
) -> None:
    cat = _category(db, owner)
    col = _collection(db, owner, "이미 포함")
    already = _item(db, user=owner, category=cat, title="이미", collection=col)
    fresh = _item(db, user=owner, category=cat, title="신규")

    response = api_client.post(
        f"/api/v1/collections/{col.id}/items",
        json={"item_ids": [str(already.id), str(fresh.id)]},
    )
    assert response.status_code == 200
    assert response.json()["added_count"] == 1
    db.refresh(fresh)
    assert fresh.collection_id == col.id


def test_add_items_conflict_when_other_collection(
    api_client: TestClient,
    db: Session,
    owner: User,
) -> None:
    cat = _category(db, owner)
    target = _collection(db, owner, "타겟")
    other = _collection(db, owner, "다른")
    unassigned = _item(db, user=owner, category=cat, title="미지정")
    assigned = _item(db, user=owner, category=cat, title="배정됨", collection=other)
    unassigned_id = unassigned.id

    response = api_client.post(
        f"/api/v1/collections/{target.id}/items",
        json={"item_ids": [str(unassigned.id), str(assigned.id)]},
    )
    assert response.status_code == 409
    db.expire_all()
    collection_id = db.scalar(select(Item.collection_id).where(Item.id == unassigned_id))
    assert collection_id is None


def test_add_items_other_user_collection_404(
    api_client: TestClient,
    db: Session,
    owner: User,
    other_user: User,
) -> None:
    cat = _category(db, owner)
    foreign = _collection(db, other_user, "남의 컬렉션")
    item = _item(db, user=owner, category=cat, title="내 항목")

    response = api_client.post(
        f"/api/v1/collections/{foreign.id}/items",
        json={"item_ids": [str(item.id)]},
    )
    assert response.status_code == 404
    db.refresh(item)
    assert item.collection_id is None


def test_add_items_other_user_item_404(
    api_client: TestClient,
    db: Session,
    owner: User,
    other_user: User,
) -> None:
    owner_cat = _category(db, owner)
    other_cat = _category(db, other_user)
    col = _collection(db, owner, "내 컬렉션")
    mine = _item(db, user=owner, category=owner_cat, title="내 것")
    foreign = _item(db, user=other_user, category=other_cat, title="남의 것")

    response = api_client.post(
        f"/api/v1/collections/{col.id}/items",
        json={"item_ids": [str(mine.id), str(foreign.id)]},
    )
    assert response.status_code == 404
    db.refresh(mine)
    assert mine.collection_id is None


def test_add_items_missing_item_404(
    api_client: TestClient,
    db: Session,
    owner: User,
) -> None:
    cat = _category(db, owner)
    col = _collection(db, owner, "타겟")
    item = _item(db, user=owner, category=cat, title="존재")

    response = api_client.post(
        f"/api/v1/collections/{col.id}/items",
        json={"item_ids": [str(item.id), str(uuid4())]},
    )
    assert response.status_code == 404
    db.refresh(item)
    assert item.collection_id is None


def test_add_items_empty_rejected(api_client: TestClient, db: Session, owner: User) -> None:
    col = _collection(db, owner, "빈")
    response = api_client.post(
        f"/api/v1/collections/{col.id}/items",
        json={"item_ids": []},
    )
    assert response.status_code == 422


def test_add_items_dedupes_duplicate_ids(
    api_client: TestClient,
    db: Session,
    owner: User,
) -> None:
    cat = _category(db, owner)
    col = _collection(db, owner, "중복")
    item = _item(db, user=owner, category=cat, title="한 번만")

    response = api_client.post(
        f"/api/v1/collections/{col.id}/items",
        json={"item_ids": [str(item.id), str(item.id)]},
    )
    assert response.status_code == 200
    assert response.json()["added_count"] == 1


def test_unassigned_item_search_filters(
    api_client: TestClient,
    db: Session,
    owner: User,
    other_user: User,
) -> None:
    cat_movie = _category(db, owner, "영화")
    cat_book = _category(db, owner, "도서")
    other_cat = _category(db, other_user, "영화")
    col = _collection(db, owner, "시리즈")
    match = _item(
        db,
        user=owner,
        category=cat_movie,
        title="오디세이",
        status=ItemStatus.PLANNED,
    )
    _item(
        db,
        user=owner,
        category=cat_movie,
        title="오디세이 완료",
        status=ItemStatus.COMPLETED,
    )
    _item(db, user=owner, category=cat_book, title="오디세이 도서")
    _item(
        db,
        user=owner,
        category=cat_movie,
        title="오디세이 배정",
        collection=col,
    )
    _item(db, user=other_user, category=other_cat, title="오디세이")

    response = api_client.get(
        "/api/v1/items",
        params={
            "search": "오디세",
            "has_collection": False,
            "category_id": str(cat_movie.id),
            "status": "PLANNED",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(match.id)
