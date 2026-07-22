"""Tests for Collection POST/PATCH write APIs (C-1)."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
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
from app.services import catalog


@pytest.fixture
def owner(db: Session) -> User:
    user = User(
        email=f"col-write-owner-{uuid4().hex[:8]}@picknext.local",
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
        email=f"col-write-other-{uuid4().hex[:8]}@picknext.local",
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


def test_post_create_collection(api_client: TestClient, db: Session, owner: User) -> None:
    summary_before = api_client.get("/api/v1/summary").json()
    response = api_client.post("/api/v1/collections", json={"name": "새 컬렉션"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "새 컬렉션"
    assert body["item_count"] == 0
    assert body["planned_count"] == 0
    assert body["completed_count"] == 0
    assert body["categories"] == []
    assert body["created_at"]
    assert body["updated_at"]

    collection_id = body["id"]
    stored = db.get(Collection, collection_id)
    assert stored is not None
    assert stored.user_id == owner.id
    assert stored.name == "새 컬렉션"

    detail = api_client.get(f"/api/v1/collections/{collection_id}")
    assert detail.status_code == 200
    assert detail.json()["name"] == "새 컬렉션"

    listed = api_client.get("/api/v1/collections", params={"search": "새 컬렉션"})
    assert listed.status_code == 200
    assert any(row["id"] == collection_id for row in listed.json()["collections"])

    summary_after = api_client.get("/api/v1/summary").json()
    assert summary_after["collection_count"] == summary_before["collection_count"] + 1


def test_post_trims_name(api_client: TestClient, db: Session) -> None:
    response = api_client.post("/api/v1/collections", json={"name": "  새 컬렉션  "})
    assert response.status_code == 201
    assert response.json()["name"] == "새 컬렉션"
    assert db.get(Collection, response.json()["id"]).name == "새 컬렉션"


@pytest.mark.parametrize(
    ("payload", "status_code"),
    [
        ({"name": ""}, 422),
        ({"name": "   "}, 422),
        ({"name": None}, 422),
        ({}, 422),
        ({"name": "x" * 201}, 422),
    ],
)
def test_post_validation_errors(api_client: TestClient, payload: dict, status_code: int) -> None:
    assert api_client.post("/api/v1/collections", json=payload).status_code == status_code


def test_post_length_boundaries(api_client: TestClient) -> None:
    assert api_client.post("/api/v1/collections", json={"name": "A"}).status_code == 201
    assert api_client.post("/api/v1/collections", json={"name": "B" * 200}).status_code == 201


def test_post_duplicate_name_409(api_client: TestClient, db: Session, owner: User) -> None:
    _collection(db, owner, "스타워즈")
    summary_before = api_client.get("/api/v1/summary").json()
    response = api_client.post("/api/v1/collections", json={"name": "스타워즈"})
    assert response.status_code == 409
    assert response.json()["detail"] == "Collection name already exists"
    summary_after = api_client.get("/api/v1/summary").json()
    assert summary_after["collection_count"] == summary_before["collection_count"]


def test_post_duplicate_name_409_no_new_row(
    api_client: TestClient, db: Session, owner: User
) -> None:
    _collection(db, owner, "스타워즈")
    from sqlalchemy import func, select

    before = db.scalar(
        select(func.count()).select_from(Collection).where(Collection.user_id == owner.id)
    )
    assert api_client.post("/api/v1/collections", json={"name": "스타워즈"}).status_code == 409
    after = db.scalar(
        select(func.count()).select_from(Collection).where(Collection.user_id == owner.id)
    )
    assert after == before


def test_post_other_user_same_name_allowed(db: Session, owner: User, other_user: User) -> None:
    _collection(db, other_user, "공유이름")
    app = create_app()

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: owner
    with TestClient(app) as client:
        response = client.post("/api/v1/collections", json={"name": "공유이름"})
        assert response.status_code == 201
        listed = client.get("/api/v1/collections")
        names = [row["name"] for row in listed.json()["collections"]]
        assert names.count("공유이름") == 1
    app.dependency_overrides.clear()


def test_post_case_sensitive_names(api_client: TestClient) -> None:
    assert api_client.post("/api/v1/collections", json={"name": "Star Wars"}).status_code == 201
    assert api_client.post("/api/v1/collections", json={"name": "star wars"}).status_code == 201


def test_post_preserves_internal_whitespace(api_client: TestClient, db: Session) -> None:
    name = "스타  워즈"
    response = api_client.post("/api/v1/collections", json={"name": name})
    assert response.status_code == 201
    assert response.json()["name"] == name
    assert db.get(Collection, response.json()["id"]).name == name


def test_patch_rename_collection(api_client: TestClient, db: Session, owner: User) -> None:
    cat_a = _category(db, owner, "A")
    cat_b = _category(db, owner, "B")
    col = _collection(db, owner, "스타워즈")
    _item(db, user=owner, category=cat_a, title="1", collection=col)
    _item(db, user=owner, category=cat_a, title="2", collection=col, status=ItemStatus.PLANNED)
    _item(db, user=owner, category=cat_b, title="3", collection=col, status=ItemStatus.COMPLETED)
    col_id = col.id
    before_updated = col.updated_at

    response = api_client.patch(
        f"/api/v1/collections/{col_id}",
        json={"name": "스타워즈 시리즈"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "스타워즈 시리즈"
    assert body["item_count"] == 3
    assert body["planned_count"] == 2
    assert body["completed_count"] == 1
    assert sum(c["item_count"] for c in body["categories"]) == 3
    assert db.get(Collection, col_id).name == "스타워즈 시리즈"
    assert body["updated_at"] >= before_updated.replace(tzinfo=None).isoformat()[:19]

    detail = api_client.get(f"/api/v1/collections/{col_id}")
    assert detail.json()["name"] == "스타워즈 시리즈"


def test_patch_trims_name(api_client: TestClient, db: Session, owner: User) -> None:
    col = _collection(db, owner, "이전")
    response = api_client.patch(
        f"/api/v1/collections/{col.id}",
        json={"name": "  변경 이름  "},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "변경 이름"
    assert db.get(Collection, col.id).name == "변경 이름"


def test_patch_noop_preserves_updated_at(api_client: TestClient, db: Session, owner: User) -> None:
    col = _collection(db, owner, "스타워즈")
    col_id = col.id
    before = col.updated_at
    bind = db.get_bind()
    statements: list[str] = []

    def before_cursor(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        statements.append(str(statement))

    event.listen(bind, "before_cursor_execute", before_cursor)
    try:
        statements.clear()
        response = api_client.patch(
            f"/api/v1/collections/{col_id}",
            json={"name": "  스타워즈  "},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "스타워즈"
        assert db.get(Collection, col_id).updated_at == before
        assert not any("UPDATE collections" in stmt.upper() for stmt in statements)
    finally:
        event.remove(bind, "before_cursor_execute", before_cursor)


def test_patch_duplicate_name_409(api_client: TestClient, db: Session, owner: User) -> None:
    _collection(db, owner, "스타워즈")
    target = _collection(db, owner, "건담")
    target_id = target.id
    before_updated = target.updated_at
    cat = _category(db, owner)
    _item(db, user=owner, category=cat, title="item", collection=target)

    response = api_client.patch(
        f"/api/v1/collections/{target_id}",
        json={"name": "스타워즈"},
    )
    assert response.status_code == 409
    stored = db.get(Collection, target_id)
    assert stored.name == "건담"
    assert stored.updated_at == before_updated
    assert stored.items[0].collection_id == target_id


def test_patch_other_user_404(db: Session, owner: User, other_user: User) -> None:
    col = _collection(db, other_user, "비공개")
    col_id = col.id
    app = create_app()

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: owner
    with TestClient(app) as client:
        response = client.patch(
            f"/api/v1/collections/{col_id}",
            json={"name": "변경"},
        )
        assert response.status_code == 404
    app.dependency_overrides.clear()
    assert db.get(Collection, col_id).name == "비공개"


def test_patch_not_found_404(api_client: TestClient) -> None:
    missing = uuid4()
    response = api_client.patch(
        f"/api/v1/collections/{missing}",
        json={"name": "없음"},
    )
    assert response.status_code == 404


def test_patch_invalid_uuid_422(api_client: TestClient) -> None:
    assert api_client.patch("/api/v1/collections/not-a-uuid", json={"name": "x"}).status_code == 422


@pytest.mark.parametrize(
    ("payload", "status_code"),
    [
        ({}, 422),
        ({"name": None}, 422),
        ({"name": ""}, 422),
        ({"name": "   "}, 422),
        ({"name": "x" * 201}, 422),
    ],
)
def test_patch_validation_errors(
    api_client: TestClient, db: Session, owner: User, payload: dict, status_code: int
) -> None:
    col = _collection(db, owner, "대상")
    assert (
        api_client.patch(f"/api/v1/collections/{col.id}", json=payload).status_code == status_code
    )


def test_patch_max_length_200(api_client: TestClient, db: Session, owner: User) -> None:
    col = _collection(db, owner, "대상")
    assert (
        api_client.patch(
            f"/api/v1/collections/{col.id}",
            json={"name": "Y" * 200},
        ).status_code
        == 200
    )


def test_create_maps_integrity_error_to_409(
    db: Session, owner: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    _collection(db, owner, "충돌")
    original_flush = db.flush

    def fail_flush() -> None:
        raise IntegrityError(
            "INSERT",
            {},
            Exception(
                'duplicate key value violates unique constraint "uq_collections_user_id_name"'
            ),
        )

    monkeypatch.setattr(db, "flush", fail_flush)
    with pytest.raises(HTTPException) as exc_info:
        catalog.create_collection(db, owner, "새이름", commit=False)
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Collection name already exists"
    monkeypatch.setattr(db, "flush", original_flush)
    catalog.create_collection(db, owner, "다른이름", commit=False)


def test_patch_maps_integrity_error_to_409(
    db: Session, owner: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    _collection(db, owner, "스타워즈")
    target = _collection(db, owner, "건담")
    target_id = target.id

    def fail_flush() -> None:
        raise IntegrityError(
            "UPDATE",
            {},
            Exception(
                'duplicate key value violates unique constraint "uq_collections_user_id_name"'
            ),
        )

    monkeypatch.setattr(db, "flush", fail_flush)
    with pytest.raises(HTTPException) as exc_info:
        catalog.update_collection(db, owner, target_id, "스타워즈", commit=False)
    assert exc_info.value.status_code == 409
    assert db.get(Collection, target_id).name == "건담"


def test_post_then_delete_empty_collection(api_client: TestClient) -> None:
    created = api_client.post("/api/v1/collections", json={"name": "임시"})
    assert created.status_code == 201
    col_id = created.json()["id"]
    assert api_client.delete(f"/api/v1/collections/{col_id}").status_code == 204
    assert api_client.get(f"/api/v1/collections/{col_id}").status_code == 404


def test_patch_then_delete_with_items_409(api_client: TestClient, db: Session, owner: User) -> None:
    cat = _category(db, owner)
    col = _collection(db, owner, "원래")
    _item(db, user=owner, category=cat, title="항목", collection=col)
    col_id = col.id
    assert (
        api_client.patch(
            f"/api/v1/collections/{col_id}",
            json={"name": "변경됨"},
        ).status_code
        == 200
    )
    assert api_client.delete(f"/api/v1/collections/{col_id}").status_code == 409
    assert db.get(Collection, col_id).name == "변경됨"
    assert db.get(Collection, col_id).items[0].title == "항목"


def test_openapi_includes_collection_write_paths(api_client: TestClient) -> None:
    paths = api_client.get("/openapi.json").json()["paths"]
    post_op = paths["/api/v1/collections"]["post"]
    patch_op = paths["/api/v1/collections/{collection_id}"]["patch"]
    assert "201" in post_op["responses"]
    assert "409" in post_op["responses"]
    assert "422" in post_op["responses"]
    assert post_op["responses"]["201"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "CollectionResponse"
    )
    assert "200" in patch_op["responses"]
    assert "404" in patch_op["responses"]
    assert "409" in patch_op["responses"]
    assert "422" in patch_op["responses"]
