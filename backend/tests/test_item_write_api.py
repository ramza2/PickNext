"""Tests for Item POST/PATCH write APIs (I-1)."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
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
    LegacyImportDisposition,
    LegacyImportItem,
    LegacyImportRun,
    LegacyImportRunStatus,
    RecommendationHistory,
    RecommendationHistoryItem,
    StatusFilter,
    User,
)


@pytest.fixture
def owner(db: Session) -> User:
    user = User(
        email=f"item-write-owner-{uuid4().hex[:8]}@picknext.local",
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
        email=f"item-write-other-{uuid4().hex[:8]}@picknext.local",
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


def _category(db: Session, user: User, name: str = "영화", sort_order: int = 1) -> Category:
    cat = Category(
        user_id=user.id,
        name=name,
        category_type=CategoryType.MEDIA,
        sort_order=sort_order,
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
    rating: Decimal = Decimal("0.0"),
    progress_note: str | None = None,
    memo: str | None = None,
) -> Item:
    item = Item(
        user_id=user.id,
        category_id=category.id,
        collection_id=collection.id if collection else None,
        title=title,
        status=status,
        rating=rating,
        progress_note=progress_note,
        memo=memo,
    )
    db.add(item)
    db.flush()
    return item


def _history(
    db: Session,
    *,
    user: User,
    category: Category,
    items: list[Item],
) -> RecommendationHistory:
    history = RecommendationHistory(
        user_id=user.id,
        category_id=category.id,
        status_filter=StatusFilter.ALL,
    )
    db.add(history)
    db.flush()
    for index, item in enumerate(items):
        db.add(
            RecommendationHistoryItem(
                recommendation_history_id=history.id,
                item_id=item.id,
                title_snapshot=item.title,
                status_at_selection=item.status,
                sort_order=index,
            )
        )
    db.flush()
    return history


def _legacy_run(db: Session, user: User) -> LegacyImportRun:
    run = LegacyImportRun(
        user_id=user.id,
        source_filename="write-test.json",
        source_sha256=uuid4().hex,
        source_total_count=1,
        imported_item_count=1,
        skipped_count=0,
        status=LegacyImportRunStatus.SUCCESS,
    )
    db.add(run)
    db.flush()
    return run


def test_post_minimal_create(api_client: TestClient, db: Session, owner: User) -> None:
    cat = _category(db, owner)
    summary_before = api_client.get("/api/v1/summary").json()
    cats_before = api_client.get("/api/v1/categories").json()["categories"]
    movie_before = next(c for c in cats_before if c["id"] == str(cat.id))

    response = api_client.post(
        "/api/v1/items",
        json={"title": "새 항목", "category_id": str(cat.id)},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "새 항목"
    assert body["status"] == "PLANNED"
    assert body["rating"] == 0.0
    assert body["progress_note"] is None
    assert body["memo"] is None
    assert body["collection"] is None
    assert body["category"]["id"] == str(cat.id)

    item_id = body["id"]
    stored = db.get(Item, item_id)
    assert stored is not None
    assert stored.user_id == owner.id
    assert stored.title == "새 항목"

    assert api_client.get(f"/api/v1/items/{item_id}").status_code == 200
    listed = api_client.get("/api/v1/items", params={"search": "새 항목"})
    assert any(row["id"] == item_id for row in listed.json()["items"])

    summary_after = api_client.get("/api/v1/summary").json()
    assert summary_after["item_count"] == summary_before["item_count"] + 1
    cats_after = api_client.get("/api/v1/categories").json()["categories"]
    movie_after = next(c for c in cats_after if c["id"] == str(cat.id))
    assert movie_after["item_count"] == movie_before["item_count"] + 1


def test_post_full_fields(api_client: TestClient, db: Session, owner: User) -> None:
    cat = _category(db, owner)
    col = _collection(db, owner, "스타워즈")
    col_before = api_client.get(f"/api/v1/collections/{col.id}").json()

    response = api_client.post(
        "/api/v1/items",
        json={
            "title": "스타워즈",
            "category_id": str(cat.id),
            "collection_id": str(col.id),
            "status": "COMPLETED",
            "rating": 4.5,
            "progress_note": "시즌 2",
            "memo": "메모",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["rating"] == 4.5
    assert body["progress_note"] == "시즌 2"
    assert body["memo"] == "메모"
    assert body["collection"]["id"] == str(col.id)

    col_after = api_client.get(f"/api/v1/collections/{col.id}").json()
    assert col_after["item_count"] == col_before["item_count"] + 1
    assert col_after["updated_at"] == col_before["updated_at"]


def test_post_title_trim_and_long_title(api_client: TestClient, db: Session, owner: User) -> None:
    cat = _category(db, owner)
    response = api_client.post(
        "/api/v1/items",
        json={"title": "  스타워즈  ", "category_id": str(cat.id)},
    )
    assert response.status_code == 201
    assert response.json()["title"] == "스타워즈"

    internal = api_client.post(
        "/api/v1/items",
        json={"title": "스타  워즈", "category_id": str(cat.id)},
    )
    assert internal.status_code == 201
    assert internal.json()["title"] == "스타  워즈"

    long_title = "X" * 321
    long_response = api_client.post(
        "/api/v1/items",
        json={"title": long_title, "category_id": str(cat.id)},
    )
    assert long_response.status_code == 201
    assert long_response.json()["title"] == long_title


@pytest.mark.parametrize(
    ("payload_extra", "status_code"),
    [
        ({"title": ""}, 422),
        ({"title": "   "}, 422),
        ({"title": None}, 422),
        ({}, 422),
    ],
)
def test_post_title_validation(
    api_client: TestClient, db: Session, owner: User, payload_extra: dict, status_code: int
) -> None:
    cat = _category(db, owner)
    payload = {"category_id": str(cat.id), **payload_extra}
    if "title" not in payload_extra and payload_extra == {}:
        payload = {"category_id": str(cat.id)}
    response = api_client.post("/api/v1/items", json=payload)
    assert response.status_code == status_code


def test_post_duplicate_title_allowed(api_client: TestClient, db: Session, owner: User) -> None:
    cat = _category(db, owner)
    _item(db, user=owner, category=cat, title="중복")
    response = api_client.post(
        "/api/v1/items",
        json={"title": "중복", "category_id": str(cat.id)},
    )
    assert response.status_code == 201


@pytest.mark.parametrize(
    ("status_value", "expected"),
    [
        (None, "PLANNED"),
        ("PLANNED", "PLANNED"),
        ("COMPLETED", "COMPLETED"),
    ],
)
def test_post_status(
    api_client: TestClient,
    db: Session,
    owner: User,
    status_value: str | None,
    expected: str,
) -> None:
    cat = _category(db, owner)
    payload: dict = {"title": "상태", "category_id": str(cat.id)}
    if status_value is not None:
        payload["status"] = status_value
    response = api_client.post("/api/v1/items", json=payload)
    assert response.status_code == 201
    assert response.json()["status"] == expected


@pytest.mark.parametrize("status_value", ["INVALID"])
def test_post_status_invalid(
    api_client: TestClient, db: Session, owner: User, status_value
) -> None:
    cat = _category(db, owner)
    payload: dict = {"title": "상태", "category_id": str(cat.id), "status": status_value}
    response = api_client.post("/api/v1/items", json=payload)
    assert response.status_code == 422


def test_post_status_null_rejected(api_client: TestClient, db: Session, owner: User) -> None:
    cat = _category(db, owner)
    response = api_client.post(
        "/api/v1/items",
        json={"title": "상태", "category_id": str(cat.id), "status": None},
    )
    assert response.status_code == 422


@pytest.mark.parametrize("rating", [0, 0.0, 0.5, 5, 5.0])
def test_post_rating_allowed(
    api_client: TestClient, db: Session, owner: User, rating: float
) -> None:
    cat = _category(db, owner)
    response = api_client.post(
        "/api/v1/items",
        json={"title": "평점", "category_id": str(cat.id), "rating": rating},
    )
    assert response.status_code == 201


@pytest.mark.parametrize("rating", [-0.5, 5.5, 1.1, 2.25, "bad"])
def test_post_rating_rejected(api_client: TestClient, db: Session, owner: User, rating) -> None:
    cat = _category(db, owner)
    response = api_client.post(
        "/api/v1/items",
        json={"title": "평점", "category_id": str(cat.id), "rating": rating},
    )
    assert response.status_code == 422


def test_post_rating_rejected_non_finite(api_client: TestClient, db: Session, owner: User) -> None:
    cat = _category(db, owner)
    for raw in ("NaN", "Infinity", "-Infinity"):
        response = api_client.post(
            "/api/v1/items",
            json={"title": "평점", "category_id": str(cat.id), "rating": raw},
        )
        assert response.status_code == 422


def test_post_optional_text(api_client: TestClient, db: Session, owner: User) -> None:
    cat = _category(db, owner)
    note = api_client.post(
        "/api/v1/items",
        json={"title": "노트", "category_id": str(cat.id), "progress_note": "  시즌 2  "},
    )
    assert note.status_code == 201
    assert note.json()["progress_note"] == "시즌 2"

    blank_note = api_client.post(
        "/api/v1/items",
        json={"title": "노트2", "category_id": str(cat.id), "progress_note": "   "},
    )
    assert blank_note.status_code == 201
    assert blank_note.json()["progress_note"] is None

    long_note = "N" * 200
    assert (
        api_client.post(
            "/api/v1/items",
            json={"title": "노트3", "category_id": str(cat.id), "progress_note": long_note},
        ).status_code
        == 201
    )
    assert (
        api_client.post(
            "/api/v1/items",
            json={"title": "노트4", "category_id": str(cat.id), "progress_note": long_note + "X"},
        ).status_code
        == 422
    )

    memo = api_client.post(
        "/api/v1/items",
        json={"title": "메모", "category_id": str(cat.id), "memo": "  줄\n바꿈  "},
    )
    assert memo.status_code == 201
    assert memo.json()["memo"] == "줄\n바꿈"


def test_post_category_and_collection_scope(
    api_client: TestClient, db: Session, owner: User, other_user: User
) -> None:
    cat = _category(db, owner)
    other_cat = _category(db, other_user, name="타카테고리")
    col = _collection(db, owner, "내컬렉션")
    other_col = _collection(db, other_user, name="타컬렉션")

    assert (
        api_client.post(
            "/api/v1/items",
            json={"title": "정상", "category_id": str(cat.id), "collection_id": str(col.id)},
        ).status_code
        == 201
    )
    assert (
        api_client.post(
            "/api/v1/items",
            json={"title": "없음", "category_id": str(uuid4())},
        ).status_code
        == 404
    )
    assert (
        api_client.post(
            "/api/v1/items",
            json={"title": "타카테", "category_id": str(other_cat.id)},
        ).status_code
        == 404
    )
    assert (
        api_client.post(
            "/api/v1/items",
            json={"title": "타컬", "category_id": str(cat.id), "collection_id": str(other_col.id)},
        ).status_code
        == 404
    )
    assert (
        api_client.post(
            "/api/v1/items",
            json={"title": "잘못", "category_id": "not-a-uuid"},
        ).status_code
        == 422
    )


def test_post_no_legacy_mapping(api_client: TestClient, db: Session, owner: User) -> None:
    cat = _category(db, owner)
    response = api_client.post(
        "/api/v1/items",
        json={"title": "신규", "category_id": str(cat.id)},
    )
    assert response.status_code == 201
    item_id = response.json()["id"]
    count = db.scalar(
        select(func.count())
        .select_from(LegacyImportItem)
        .where(LegacyImportItem.item_id == item_id)
    )
    assert count == 0


def test_patch_single_fields(api_client: TestClient, db: Session, owner: User) -> None:
    cat_a = _category(db, owner, name="A", sort_order=1)
    cat_b = _category(db, owner, name="B", sort_order=2)
    col_a = _collection(db, owner, "컬A")
    col_b = _collection(db, owner, "컬B")
    item = _item(
        db,
        user=owner,
        category=cat_a,
        title="원본",
        collection=col_a,
        status=ItemStatus.PLANNED,
        rating=Decimal("1.0"),
        progress_note="노트",
        memo="메모",
    )
    item_id = item.id

    assert api_client.patch(f"/api/v1/items/{item_id}", json={"title": "변경"}).status_code == 200
    assert api_client.get(f"/api/v1/items/{item_id}").json()["title"] == "변경"

    assert (
        api_client.patch(
            f"/api/v1/items/{item_id}", json={"category_id": str(cat_b.id)}
        ).status_code
        == 200
    )
    assert api_client.get(f"/api/v1/items/{item_id}").json()["category"]["id"] == str(cat_b.id)

    assert (
        api_client.patch(
            f"/api/v1/items/{item_id}", json={"collection_id": str(col_b.id)}
        ).status_code
        == 200
    )
    assert api_client.get(f"/api/v1/items/{item_id}").json()["collection"]["id"] == str(col_b.id)

    assert (
        api_client.patch(f"/api/v1/items/{item_id}", json={"status": "COMPLETED"}).status_code
        == 200
    )
    assert api_client.get(f"/api/v1/items/{item_id}").json()["status"] == "COMPLETED"

    assert api_client.patch(f"/api/v1/items/{item_id}", json={"rating": 4.5}).status_code == 200
    assert api_client.get(f"/api/v1/items/{item_id}").json()["rating"] == 4.5

    assert (
        api_client.patch(f"/api/v1/items/{item_id}", json={"progress_note": "새노트"}).status_code
        == 200
    )
    assert api_client.get(f"/api/v1/items/{item_id}").json()["progress_note"] == "새노트"

    assert api_client.patch(f"/api/v1/items/{item_id}", json={"memo": "새메모"}).status_code == 200
    assert api_client.get(f"/api/v1/items/{item_id}").json()["memo"] == "새메모"


def test_patch_empty_body_and_null_rules(api_client: TestClient, db: Session, owner: User) -> None:
    cat = _category(db, owner)
    item = _item(db, user=owner, category=cat, title="대상")
    item_id = item.id

    assert api_client.patch(f"/api/v1/items/{item_id}", json={}).status_code == 422
    assert (
        api_client.patch(f"/api/v1/items/{item_id}", json={"collection_id": None}).status_code
        == 200
    )
    assert (
        api_client.patch(f"/api/v1/items/{item_id}", json={"progress_note": None}).status_code
        == 200
    )
    assert api_client.patch(f"/api/v1/items/{item_id}", json={"memo": None}).status_code == 200

    for field in ("title", "category_id", "status", "rating"):
        assert api_client.patch(f"/api/v1/items/{item_id}", json={field: None}).status_code == 422


def test_patch_noop_preserves_updated_at(api_client: TestClient, db: Session, owner: User) -> None:
    cat = _category(db, owner)
    item = _item(db, user=owner, category=cat, title="기존 제목")
    item_id = item.id
    before = item.updated_at
    bind = db.get_bind()
    statements: list[str] = []

    def before_cursor(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        statements.append(str(statement))

    event.listen(bind, "before_cursor_execute", before_cursor)
    try:
        statements.clear()
        response = api_client.patch(
            f"/api/v1/items/{item_id}",
            json={"title": "  기존 제목  "},
        )
        assert response.status_code == 200
        assert db.get(Item, item_id).updated_at == before
        assert not any("UPDATE items" in stmt.upper() for stmt in statements)
    finally:
        event.remove(bind, "before_cursor_execute", before_cursor)


def test_patch_collection_attach_detach_move(
    api_client: TestClient, db: Session, owner: User
) -> None:
    cat = _category(db, owner)
    col_a = _collection(db, owner, "A")
    col_b = _collection(db, owner, "B")
    item = _item(db, user=owner, category=cat, title="이동")
    item_id = item.id
    col_a_before = api_client.get(f"/api/v1/collections/{col_a.id}").json()

    attach = api_client.patch(
        f"/api/v1/items/{item_id}",
        json={"collection_id": str(col_a.id)},
    )
    assert attach.status_code == 200
    col_a_after_attach = api_client.get(f"/api/v1/collections/{col_a.id}").json()
    assert col_a_after_attach["item_count"] == col_a_before["item_count"] + 1
    assert col_a_after_attach["updated_at"] == col_a_before["updated_at"]

    move = api_client.patch(
        f"/api/v1/items/{item_id}",
        json={"collection_id": str(col_b.id)},
    )
    assert move.status_code == 200
    col_a_after_move = api_client.get(f"/api/v1/collections/{col_a.id}").json()
    assert col_a_after_move["item_count"] == 0
    assert col_a_after_move["updated_at"] == col_a_before["updated_at"]
    assert api_client.get(f"/api/v1/collections/{col_a.id}").status_code == 200

    detach = api_client.patch(f"/api/v1/items/{item_id}", json={"collection_id": None})
    assert detach.status_code == 200
    assert api_client.get(f"/api/v1/collections/{col_a.id}").status_code == 200
    assert api_client.get(f"/api/v1/collections/{col_b.id}").json()["item_count"] == 0


def test_patch_category_change_keeps_collection(
    api_client: TestClient, db: Session, owner: User
) -> None:
    cat_a = _category(db, owner, name="A", sort_order=1)
    cat_b = _category(db, owner, name="B", sort_order=2)
    col = _collection(db, owner, "공유")
    item = _item(db, user=owner, category=cat_a, title="혼재", collection=col)
    item_id = item.id
    col_before = api_client.get(f"/api/v1/collections/{col.id}").json()

    response = api_client.patch(
        f"/api/v1/items/{item_id}",
        json={"category_id": str(cat_b.id)},
    )
    assert response.status_code == 200
    body = api_client.get(f"/api/v1/items/{item_id}").json()
    assert body["category"]["id"] == str(cat_b.id)
    assert body["collection"]["id"] == str(col.id)

    col_after = api_client.get(f"/api/v1/collections/{col.id}").json()
    assert col_after["updated_at"] == col_before["updated_at"]
    category_ids = {row["id"] for row in col_after["categories"]}
    assert str(cat_b.id) in category_ids


def test_patch_history_snapshot_unchanged(api_client: TestClient, db: Session, owner: User) -> None:
    cat = _category(db, owner)
    item = _item(db, user=owner, category=cat, title="스냅샷", status=ItemStatus.PLANNED)
    history = _history(db, user=owner, category=cat, items=[item])
    history_item = db.scalar(
        select(RecommendationHistoryItem).where(
            RecommendationHistoryItem.recommendation_history_id == history.id
        )
    )
    assert history_item is not None
    snapshot_title = history_item.title_snapshot
    snapshot_status = history_item.status_at_selection

    response = api_client.patch(
        f"/api/v1/items/{item.id}",
        json={"title": "변경됨", "status": "COMPLETED"},
    )
    assert response.status_code == 200
    db.refresh(history_item)
    assert history_item.title_snapshot == snapshot_title
    assert history_item.status_at_selection == snapshot_status
    assert db.get(RecommendationHistory, history.id) is not None


def test_patch_legacy_mapping_preserved(api_client: TestClient, db: Session, owner: User) -> None:
    cat = _category(db, owner)
    item = _item(db, user=owner, category=cat, title="레거시")
    run = _legacy_run(db, owner)
    mapping = LegacyImportItem(
        import_run_id=run.id,
        item_id=item.id,
        source_id=77,
        disposition=LegacyImportDisposition.IMPORTED,
    )
    db.add(mapping)
    db.flush()
    mapping_id = mapping.id
    imported_count = run.imported_item_count

    response = api_client.patch(
        f"/api/v1/items/{item.id}",
        json={"title": "변경", "category_id": str(cat.id)},
    )
    assert response.status_code == 200
    stored = db.get(LegacyImportItem, mapping_id)
    assert stored is not None
    assert stored.item_id == item.id
    assert stored.source_id == 77
    assert db.get(LegacyImportRun, run.id).imported_item_count == imported_count


def test_delete_regression_after_write(api_client: TestClient, db: Session, owner: User) -> None:
    cat = _category(db, owner)
    col = _collection(db, owner, "삭제컬")
    create = api_client.post(
        "/api/v1/items",
        json={"title": "삭제대상", "category_id": str(cat.id), "collection_id": str(col.id)},
    )
    assert create.status_code == 201
    item_id = create.json()["id"]
    assert api_client.delete(f"/api/v1/items/{item_id}").status_code == 204
    assert api_client.get(f"/api/v1/items/{item_id}").status_code == 404
    assert api_client.get(f"/api/v1/collections/{col.id}").status_code == 404

    col2 = _collection(db, owner, "유지컬")
    create2 = api_client.post(
        "/api/v1/items",
        json={"title": "해제", "category_id": str(cat.id), "collection_id": str(col2.id)},
    )
    item2_id = create2.json()["id"]
    assert (
        api_client.patch(f"/api/v1/items/{item2_id}", json={"collection_id": None}).status_code
        == 200
    )
    assert api_client.get(f"/api/v1/collections/{col2.id}").status_code == 200
    assert api_client.delete(f"/api/v1/collections/{col2.id}").status_code == 204

    col_a = _collection(db, owner, "이동A")
    col_b = _collection(db, owner, "이동B")
    create3 = api_client.post(
        "/api/v1/items",
        json={"title": "이동", "category_id": str(cat.id), "collection_id": str(col_a.id)},
    )
    item3_id = create3.json()["id"]
    assert (
        api_client.patch(
            f"/api/v1/items/{item3_id}", json={"collection_id": str(col_b.id)}
        ).status_code
        == 200
    )
    assert api_client.get(f"/api/v1/collections/{col_a.id}").status_code == 200
    assert api_client.delete(f"/api/v1/collections/{col_a.id}").status_code == 204
    assert api_client.delete(f"/api/v1/collections/{col_b.id}").status_code == 409


def test_patch_item_scope(
    api_client: TestClient, db: Session, owner: User, other_user: User
) -> None:
    cat = _category(db, owner)
    other_cat = _category(db, other_user, name="타")
    item = _item(db, user=owner, category=cat, title="내항목")
    other_item = _item(db, user=other_user, category=other_cat, title="타항목")

    assert (
        api_client.patch(f"/api/v1/items/{other_item.id}", json={"title": "x"}).status_code == 404
    )
    assert api_client.patch(f"/api/v1/items/{uuid4()}", json={"title": "x"}).status_code == 404
    assert api_client.patch("/api/v1/items/not-a-uuid", json={"title": "x"}).status_code == 422

    before_title = item.title
    assert (
        api_client.patch(
            f"/api/v1/items/{item.id}",
            json={"title": "ok", "category_id": str(uuid4())},
        ).status_code
        == 404
    )
    assert db.get(Item, item.id).title == before_title


def test_openapi_includes_item_write_paths(api_client: TestClient) -> None:
    paths = api_client.get("/openapi.json").json()["paths"]
    post = paths["/api/v1/items"]["post"]
    patch = paths["/api/v1/items/{item_id}"]["patch"]
    assert post["responses"]["201"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "ItemDetailResponse"
    )
    assert "404" in post["responses"]
    assert "409" in post["responses"]
    assert "422" in post["responses"]
    assert patch["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "ItemDetailResponse"
    )
    assert "404" in patch["responses"]
    assert "409" in patch["responses"]
    assert "422" in patch["responses"]
