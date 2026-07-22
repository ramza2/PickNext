"""Tests for Item Hard Delete (D-3~D-5)."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
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
    LegacyImportCollection,
    LegacyImportDisposition,
    LegacyImportItem,
    LegacyImportRun,
    LegacyImportRunStatus,
    RecommendationHistory,
    RecommendationHistoryItem,
    StatusFilter,
    User,
)
from app.services import catalog


@pytest.fixture
def owner(db: Session) -> User:
    user = User(
        email=f"del-owner-{uuid4().hex[:8]}@picknext.local",
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
        email=f"del-other-{uuid4().hex[:8]}@picknext.local",
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


def _history(
    db: Session,
    *,
    user: User,
    category: Category,
    items: list[Item],
    collection: Collection | None = None,
) -> RecommendationHistory:
    history = RecommendationHistory(
        user_id=user.id,
        category_id=category.id,
        status_filter=StatusFilter.ALL,
        collection_id=collection.id if collection else None,
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
        source_filename="delete-test.json",
        source_sha256=uuid4().hex,
        source_total_count=1,
        imported_item_count=1,
        skipped_count=0,
        status=LegacyImportRunStatus.SUCCESS,
    )
    db.add(run)
    db.flush()
    return run


def test_delete_owned_item_no_collection(api_client: TestClient, db: Session, owner: User) -> None:
    cat = _category(db, owner)
    item = _item(db, user=owner, category=cat, title="단독항목")
    item_id = item.id

    before = api_client.get("/api/v1/summary").json()
    response = api_client.delete(f"/api/v1/items/{item_id}")
    assert response.status_code == 204
    assert response.content == b""

    assert db.get(Item, item_id) is None
    assert api_client.get(f"/api/v1/items/{item_id}").status_code == 404
    listed = api_client.get("/api/v1/items", params={"page_size": 100}).json()
    assert all(row["id"] != str(item_id) for row in listed["items"])

    after = api_client.get("/api/v1/summary").json()
    assert after["item_count"] == before["item_count"] - 1
    cats = api_client.get("/api/v1/categories").json()["categories"]
    movie = next(c for c in cats if c["name"] == "영화")
    assert movie["item_count"] == 0


def test_delete_other_user_item_is_404(
    api_client: TestClient, db: Session, owner: User, other_user: User
) -> None:
    other_cat = _category(db, other_user, name="타영화")
    other_item = _item(db, user=other_user, category=other_cat, title="타유저")
    other_id = other_item.id

    assert api_client.delete(f"/api/v1/items/{other_id}").status_code == 404
    assert db.get(Item, other_id) is not None


def test_delete_missing_and_invalid_uuid(api_client: TestClient) -> None:
    assert api_client.delete(f"/api/v1/items/{uuid4()}").status_code == 404
    assert api_client.delete("/api/v1/items/not-a-uuid").status_code == 422


def test_delete_twice_second_is_404(api_client: TestClient, db: Session, owner: User) -> None:
    cat = _category(db, owner)
    item = _item(db, user=owner, category=cat, title="재삭제")
    item_id = item.id
    assert api_client.delete(f"/api/v1/items/{item_id}").status_code == 204
    assert api_client.delete(f"/api/v1/items/{item_id}").status_code == 404


def test_delete_without_history(api_client: TestClient, db: Session, owner: User) -> None:
    cat = _category(db, owner)
    item = _item(db, user=owner, category=cat, title="이력없음")
    assert api_client.delete(f"/api/v1/items/{item.id}").status_code == 204
    assert db.get(Item, item.id) is None


def test_delete_removes_whole_histories_keeps_sibling_items(
    api_client: TestClient, db: Session, owner: User
) -> None:
    cat = _category(db, owner)
    a = _item(db, user=owner, category=cat, title="A")
    b = _item(db, user=owner, category=cat, title="B")
    c = _item(db, user=owner, category=cat, title="C")
    d = _item(db, user=owner, category=cat, title="D")
    e = _item(db, user=owner, category=cat, title="E")

    r1 = _history(db, user=owner, category=cat, items=[a, b, c])
    r2 = _history(db, user=owner, category=cat, items=[a, d])
    r3 = _history(db, user=owner, category=cat, items=[e])
    r1_id, r2_id, r3_id = r1.id, r2.id, r3.id

    assert api_client.delete(f"/api/v1/items/{a.id}").status_code == 204

    assert db.get(RecommendationHistory, r1_id) is None
    assert db.get(RecommendationHistory, r2_id) is None
    assert db.get(RecommendationHistory, r3_id) is not None
    assert (
        db.scalar(
            select(func.count())
            .select_from(RecommendationHistoryItem)
            .where(RecommendationHistoryItem.recommendation_history_id.in_([r1_id, r2_id]))
        )
        == 0
    )
    assert db.get(Item, a.id) is None
    assert db.get(Item, b.id) is not None
    assert db.get(Item, c.id) is not None
    assert db.get(Item, d.id) is not None
    assert db.get(Item, e.id) is not None


def test_delete_cascades_legacy_item_mapping(
    api_client: TestClient, db: Session, owner: User
) -> None:
    cat = _category(db, owner)
    keep = _item(db, user=owner, category=cat, title="유지")
    target = _item(db, user=owner, category=cat, title="삭제대상")
    run = _legacy_run(db, owner)
    imported_count = run.imported_item_count
    mapping = LegacyImportItem(
        import_run_id=run.id,
        item_id=target.id,
        source_id=101,
        disposition=LegacyImportDisposition.IMPORTED,
    )
    keep_mapping = LegacyImportItem(
        import_run_id=run.id,
        item_id=keep.id,
        source_id=102,
        disposition=LegacyImportDisposition.IMPORTED,
    )
    db.add_all([mapping, keep_mapping])
    db.flush()
    mapping_id = mapping.id
    keep_mapping_id = keep_mapping.id
    run_id = run.id

    assert api_client.delete(f"/api/v1/items/{target.id}").status_code == 204
    assert db.get(LegacyImportItem, mapping_id) is None
    assert db.get(LegacyImportItem, keep_mapping_id) is not None
    run_after = db.get(LegacyImportRun, run_id)
    assert run_after is not None
    assert run_after.imported_item_count == imported_count


def test_delete_non_last_collection_item_keeps_collection(
    api_client: TestClient, db: Session, owner: User
) -> None:
    cat = _category(db, owner)
    col = _collection(db, owner, "시리즈")
    first = _item(db, user=owner, category=cat, title="1화", collection=col)
    second = _item(db, user=owner, category=cat, title="2화", collection=col)
    col_id = col.id

    assert api_client.delete(f"/api/v1/items/{first.id}").status_code == 204
    assert db.get(Collection, col_id) is not None
    assert db.get(Item, second.id).collection_id == col_id
    detail = api_client.get(f"/api/v1/collections/{col_id}").json()
    assert detail["item_count"] == 1
    assert detail["planned_count"] == 1


def test_delete_last_collection_item_removes_collection(
    api_client: TestClient, db: Session, owner: User
) -> None:
    cat = _category(db, owner)
    col = _collection(db, owner, "단편")
    only = _item(db, user=owner, category=cat, title="유일", collection=col)
    col_id = col.id
    item_id = only.id

    assert api_client.delete(f"/api/v1/items/{item_id}").status_code == 204
    assert db.get(Item, item_id) is None
    assert db.get(Collection, col_id) is None
    assert api_client.get(f"/api/v1/collections/{col_id}").status_code == 404


def test_delete_two_items_second_removes_collection(
    api_client: TestClient, db: Session, owner: User
) -> None:
    cat = _category(db, owner)
    col = _collection(db, owner, "두편")
    first = _item(db, user=owner, category=cat, title="A", collection=col)
    second = _item(db, user=owner, category=cat, title="B", collection=col)
    col_id = col.id

    assert api_client.delete(f"/api/v1/items/{first.id}").status_code == 204
    assert api_client.get(f"/api/v1/collections/{col_id}").status_code == 200
    assert api_client.delete(f"/api/v1/items/{second.id}").status_code == 204
    assert api_client.get(f"/api/v1/collections/{col_id}").status_code == 404


def test_last_item_delete_nulls_unrelated_history_collection_fk(
    api_client: TestClient, db: Session, owner: User
) -> None:
    cat = _category(db, owner)
    col = _collection(db, owner, "콜렉션")
    only = _item(db, user=owner, category=cat, title="마지막", collection=col)
    other = _item(db, user=owner, category=cat, title="외부")
    history = _history(db, user=owner, category=cat, items=[other], collection=col)
    history_id = history.id
    col_id = col.id

    assert api_client.delete(f"/api/v1/items/{only.id}").status_code == 204
    assert db.get(Collection, col_id) is None
    kept = db.get(RecommendationHistory, history_id)
    assert kept is not None
    assert kept.collection_id is None
    assert kept.items[0].title_snapshot == "외부"


def test_last_item_delete_cascades_legacy_collection_mapping(
    api_client: TestClient, db: Session, owner: User
) -> None:
    cat = _category(db, owner)
    col = _collection(db, owner, "레거시콜")
    keep_col = _collection(db, owner, "유지콜")
    only = _item(db, user=owner, category=cat, title="유일", collection=col)
    run = _legacy_run(db, owner)
    mapping = LegacyImportCollection(
        import_run_id=run.id,
        collection_id=col.id,
        collection_name=col.name,
    )
    keep_mapping = LegacyImportCollection(
        import_run_id=run.id,
        collection_id=keep_col.id,
        collection_name=keep_col.name,
    )
    db.add_all([mapping, keep_mapping])
    db.flush()
    mapping_id = mapping.id
    keep_id = keep_mapping.id

    assert api_client.delete(f"/api/v1/items/{only.id}").status_code == 204
    assert db.get(LegacyImportCollection, mapping_id) is None
    assert db.get(LegacyImportCollection, keep_id) is not None


def test_empty_collection_untouched_by_unrelated_item_delete(
    api_client: TestClient, db: Session, owner: User
) -> None:
    cat = _category(db, owner)
    empty = _collection(db, owner, "빈컬렉션")
    lone = _item(db, user=owner, category=cat, title="무소속")
    empty_id = empty.id

    assert api_client.delete(f"/api/v1/items/{lone.id}").status_code == 204
    assert db.get(Collection, empty_id) is not None
    assert api_client.get(f"/api/v1/collections/{empty_id}").json()["item_count"] == 0


def test_delete_does_not_touch_collection_updated_at(
    api_client: TestClient, db: Session, owner: User
) -> None:
    cat = _category(db, owner)
    col = _collection(db, owner, "터치금지")
    first = _item(db, user=owner, category=cat, title="1", collection=col)
    _item(db, user=owner, category=cat, title="2", collection=col)
    before = col.updated_at

    assert api_client.delete(f"/api/v1/items/{first.id}").status_code == 204
    db.refresh(col)
    assert col.updated_at == before


def test_delete_query_count_stable_with_many_histories(
    api_client: TestClient, db: Session, owner: User
) -> None:
    cat = _category(db, owner)
    target = _item(db, user=owner, category=cat, title="타깃")
    sibling = _item(db, user=owner, category=cat, title="형제")
    for i in range(5):
        _history(db, user=owner, category=cat, items=[target, sibling])

    statements: list[str] = []
    bind = db.get_bind()

    def before_cursor(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        statements.append(str(statement))

    event.listen(bind, "before_cursor_execute", before_cursor)
    try:
        statements.clear()
        assert api_client.delete(f"/api/v1/items/{target.id}").status_code == 204
        # Should not scale with history item rows (no per-history SELECT loops).
        assert len(statements) <= 12
    finally:
        event.remove(bind, "before_cursor_execute", before_cursor)


def test_delete_maps_integrity_error_to_409(
    db: Session, owner: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    cat = _category(db, owner)
    item = _item(db, user=owner, category=cat, title="충돌")
    item_id = item.id

    def fail_commit() -> None:
        raise IntegrityError("DELETE", {}, Exception("fk"))

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(HTTPException) as exc_info:
        catalog.delete_item(db, owner, item_id)
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Conflict while deleting item"


def test_openapi_includes_item_delete(api_client: TestClient) -> None:
    paths = api_client.get("/openapi.json").json()["paths"]
    delete_op = paths["/api/v1/items/{item_id}"]["delete"]
    assert "204" in delete_op["responses"]
    assert "404" in delete_op["responses"]
    content = delete_op["responses"]["204"].get("content")
    assert content in (None, {})
