"""Tests for Collection direct Hard Delete (D-6)."""

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
    LegacyImportCollection,
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
        email=f"col-del-owner-{uuid4().hex[:8]}@picknext.local",
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
        email=f"col-del-other-{uuid4().hex[:8]}@picknext.local",
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
        source_filename="col-delete-test.json",
        source_sha256=uuid4().hex,
        source_total_count=1,
        imported_item_count=1,
        skipped_count=0,
        status=LegacyImportRunStatus.SUCCESS,
    )
    db.add(run)
    db.flush()
    return run


def test_delete_empty_collection(
    api_client: TestClient, db: Session, owner: User
) -> None:
    col = _collection(db, owner, "빈컬렉션")
    col_id = col.id

    response = api_client.delete(f"/api/v1/collections/{col_id}")
    assert response.status_code == 204
    assert response.content == b""

    assert db.get(Collection, col_id) is None
    assert api_client.get(f"/api/v1/collections/{col_id}").status_code == 404
    listed = api_client.get("/api/v1/collections", params={"page_size": 100}).json()
    assert all(row["id"] != str(col_id) for row in listed["collections"])


def test_delete_collection_with_one_item_returns_409(
    api_client: TestClient, db: Session, owner: User
) -> None:
    cat = _category(db, owner)
    col = _collection(db, owner, "단일")
    item = _item(db, user=owner, category=cat, title="유일", collection=col)
    col_id = col.id
    item_id = item.id

    before_summary = api_client.get("/api/v1/summary").json()
    before_detail = api_client.get(f"/api/v1/collections/{col_id}").json()

    response = api_client.delete(f"/api/v1/collections/{col_id}")
    assert response.status_code == 409
    assert response.json()["detail"] == "Collection contains items"

    assert db.get(Collection, col_id) is not None
    kept = db.get(Item, item_id)
    assert kept is not None
    assert kept.collection_id == col_id

    detail = api_client.get(f"/api/v1/collections/{col_id}").json()
    assert detail["item_count"] == 1
    assert detail["planned_count"] == before_detail["planned_count"]
    assert detail["categories"] == before_detail["categories"]

    after_summary = api_client.get("/api/v1/summary").json()
    assert after_summary["item_count"] == before_summary["item_count"]


def test_delete_collection_with_many_items_returns_409(
    api_client: TestClient, db: Session, owner: User
) -> None:
    cat = _category(db, owner)
    col = _collection(db, owner, "다중")
    first = _item(db, user=owner, category=cat, title="1", collection=col)
    second = _item(db, user=owner, category=cat, title="2", collection=col)
    col_id = col.id

    assert api_client.delete(f"/api/v1/collections/{col_id}").status_code == 409
    assert db.get(Collection, col_id) is not None
    assert db.get(Item, first.id).collection_id == col_id
    assert db.get(Item, second.id).collection_id == col_id


def test_delete_other_user_collection_is_404(
    api_client: TestClient, db: Session, other_user: User
) -> None:
    other_cat = _category(db, other_user, name="타영화")
    other_col = _collection(db, other_user, "타콜")
    _item(db, user=other_user, category=other_cat, title="타항", collection=other_col)
    col_id = other_col.id

    assert api_client.delete(f"/api/v1/collections/{col_id}").status_code == 404
    assert db.get(Collection, col_id) is not None


def test_delete_missing_and_invalid_uuid(api_client: TestClient) -> None:
    assert api_client.delete(f"/api/v1/collections/{uuid4()}").status_code == 404
    assert api_client.delete("/api/v1/collections/not-a-uuid").status_code == 422


def test_delete_twice_second_is_404(api_client: TestClient, db: Session, owner: User) -> None:
    col = _collection(db, owner, "재삭제")
    col_id = col.id
    assert api_client.delete(f"/api/v1/collections/{col_id}").status_code == 204
    assert api_client.delete(f"/api/v1/collections/{col_id}").status_code == 404


def test_delete_does_not_unlink_items_on_409(
    api_client: TestClient, db: Session, owner: User
) -> None:
    cat = _category(db, owner)
    col = _collection(db, owner, "unlink금지")
    item = _item(db, user=owner, category=cat, title="연결", collection=col)
    col_id = col.id
    item_id = item.id

    statements: list[str] = []
    bind = db.get_bind()

    def before_cursor(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        statements.append(str(statement))

    event.listen(bind, "before_cursor_execute", before_cursor)
    try:
        assert api_client.delete(f"/api/v1/collections/{col_id}").status_code == 409
        update_items = [s for s in statements if "UPDATE" in s.upper() and "items" in s.lower()]
        assert update_items == []
    finally:
        event.remove(bind, "before_cursor_execute", before_cursor)

    assert db.get(Item, item_id).collection_id == col_id


def test_delete_empty_collection_nulls_history_collection_fk(
    api_client: TestClient, db: Session, owner: User
) -> None:
    cat = _category(db, owner)
    col = _collection(db, owner, "히스토리참조")
    other = _item(db, user=owner, category=cat, title="외부")
    history = _history(db, user=owner, category=cat, items=[other], collection=col)
    other_history = _history(db, user=owner, category=cat, items=[other])
    history_id = history.id
    other_history_id = other_history.id
    col_id = col.id

    assert api_client.delete(f"/api/v1/collections/{col_id}").status_code == 204
    assert db.get(Collection, col_id) is None

    kept = db.get(RecommendationHistory, history_id)
    assert kept is not None
    assert kept.collection_id is None
    assert len(kept.items) == 1

    other_kept = db.get(RecommendationHistory, other_history_id)
    assert other_kept is not None
    assert other_kept.collection_id is None


def test_delete_with_items_does_not_change_history(
    api_client: TestClient, db: Session, owner: User
) -> None:
    cat = _category(db, owner)
    col = _collection(db, owner, "항목있음")
    item = _item(db, user=owner, category=cat, title="내부", collection=col)
    history = _history(db, user=owner, category=cat, items=[item], collection=col)
    history_id = history.id
    col_id = col.id

    assert api_client.delete(f"/api/v1/collections/{col_id}").status_code == 409
    kept = db.get(RecommendationHistory, history_id)
    assert kept is not None
    assert kept.collection_id == col_id


def test_delete_empty_collection_cascades_legacy_mapping(
    api_client: TestClient, db: Session, owner: User
) -> None:
    col = _collection(db, owner, "레거시빈")
    keep_col = _collection(db, owner, "유지")
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
    run_id = run.id
    imported_count = run.imported_item_count

    assert api_client.delete(f"/api/v1/collections/{col.id}").status_code == 204
    assert db.get(LegacyImportCollection, mapping_id) is None
    assert db.get(LegacyImportCollection, keep_id) is not None
    run_after = db.get(LegacyImportRun, run_id)
    assert run_after is not None
    assert run_after.imported_item_count == imported_count


def test_delete_with_items_keeps_legacy_mapping(
    api_client: TestClient, db: Session, owner: User
) -> None:
    cat = _category(db, owner)
    col = _collection(db, owner, "레거시항목")
    _item(db, user=owner, category=cat, title="연결", collection=col)
    run = _legacy_run(db, owner)
    mapping = LegacyImportCollection(
        import_run_id=run.id,
        collection_id=col.id,
        collection_name=col.name,
    )
    db.add(mapping)
    db.flush()
    mapping_id = mapping.id

    assert api_client.delete(f"/api/v1/collections/{col.id}").status_code == 409
    assert db.get(LegacyImportCollection, mapping_id) is not None


def test_delete_does_not_touch_collection_updated_at_on_409(
    api_client: TestClient, db: Session, owner: User
) -> None:
    cat = _category(db, owner)
    col = _collection(db, owner, "터치금지")
    _item(db, user=owner, category=cat, title="1", collection=col)
    before = col.updated_at

    assert api_client.delete(f"/api/v1/collections/{col.id}").status_code == 409
    db.refresh(col)
    assert col.updated_at == before


def test_delete_query_count_stable_for_empty_collection(
    api_client: TestClient, db: Session, owner: User
) -> None:
    cat = _category(db, owner)
    col = _collection(db, owner, "쿼리")
    other = _item(db, user=owner, category=cat, title="무관")
    _history(db, user=owner, category=cat, items=[other], collection=col)
    run = _legacy_run(db, owner)
    db.add(
        LegacyImportCollection(
            import_run_id=run.id,
            collection_id=col.id,
            collection_name=col.name,
        )
    )
    db.flush()

    statements: list[str] = []
    bind = db.get_bind()

    def before_cursor(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        statements.append(str(statement))

    event.listen(bind, "before_cursor_execute", before_cursor)
    try:
        statements.clear()
        assert api_client.delete(f"/api/v1/collections/{col.id}").status_code == 204
        assert len(statements) <= 8
    finally:
        event.remove(bind, "before_cursor_execute", before_cursor)


def test_delete_maps_integrity_error_to_409(
    db: Session, owner: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    col = _collection(db, owner, "충돌")
    col_id = col.id

    def fail_commit() -> None:
        raise IntegrityError("DELETE", {}, Exception("fk"))

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(HTTPException) as exc_info:
        catalog.delete_collection(db, owner, col_id)
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Collection contains items"


def test_item_delete_still_auto_removes_last_item_collection(
    api_client: TestClient, db: Session, owner: User
) -> None:
    """Regression: Item DELETE path must still auto-delete empty collections."""
    cat = _category(db, owner)
    col = _collection(db, owner, "마지막항목")
    only = _item(db, user=owner, category=cat, title="유일", collection=col)
    col_id = col.id

    assert api_client.delete(f"/api/v1/items/{only.id}").status_code == 204
    assert db.get(Collection, col_id) is None
    assert api_client.delete(f"/api/v1/collections/{col_id}").status_code == 404


def test_openapi_includes_collection_delete(api_client: TestClient) -> None:
    paths = api_client.get("/openapi.json").json()["paths"]
    delete_op = paths["/api/v1/collections/{collection_id}"]["delete"]
    assert "204" in delete_op["responses"]
    assert "404" in delete_op["responses"]
    assert "409" in delete_op["responses"]
    content = delete_op["responses"]["204"].get("content")
    assert content in (None, {})
