"""Tests for Category·Item read APIs (Phase A-1)."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
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
        email=f"owner-{uuid4().hex[:8]}@picknext.local",
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
        email=f"other-{uuid4().hex[:8]}@picknext.local",
        display_name="Other",
        password_hash="hash",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def catalog_data(db: Session, owner: User, other_user: User) -> dict:
    movie = Category(
        user_id=owner.id,
        name="영화",
        category_type=CategoryType.MEDIA,
        sort_order=3,
    )
    empty = Category(
        user_id=owner.id,
        name="빈카테고리",
        category_type=CategoryType.GENERAL,
        sort_order=99,
    )
    other_cat = Category(
        user_id=other_user.id,
        name="영화",
        category_type=CategoryType.MEDIA,
        sort_order=1,
    )
    db.add_all([movie, empty, other_cat])
    db.flush()

    col = Collection(user_id=owner.id, name="007 시리즈")
    other_col = Collection(user_id=other_user.id, name="타유저컬렉션")
    db.add_all([col, other_col])
    db.flush()

    long_title = "X" * 321
    assert len(long_title) == 321

    items = [
        Item(
            user_id=owner.id,
            category_id=movie.id,
            collection_id=col.id,
            title="007 골드핑거",
            status=ItemStatus.COMPLETED,
            rating=Decimal("4.5"),
            progress_note=None,
            memo=None,
        ),
        Item(
            user_id=owner.id,
            category_id=movie.id,
            collection_id=None,
            title="기생충",
            status=ItemStatus.PLANNED,
            rating=Decimal("0.0"),
            progress_note=None,
            memo="메모",
        ),
        Item(
            user_id=owner.id,
            category_id=movie.id,
            collection_id=None,
            title=long_title,
            status=ItemStatus.PLANNED,
            rating=Decimal("0.0"),
        ),
        Item(
            user_id=owner.id,
            category_id=movie.id,
            collection_id=None,
            title="100%_escape\\test",
            status=ItemStatus.COMPLETED,
            rating=Decimal("1.0"),
        ),
        Item(
            user_id=other_user.id,
            category_id=other_cat.id,
            title="타유저영화",
            status=ItemStatus.PLANNED,
            rating=Decimal("5.0"),
        ),
    ]
    db.add_all(items)
    db.flush()

    return {
        "owner": owner,
        "other_user": other_user,
        "movie": movie,
        "empty": empty,
        "col": col,
        "items": {item.title: item for item in items if item.user_id == owner.id},
        "other_item": items[4],
        "long_title": long_title,
    }


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


def test_summary_counts(api_client: TestClient, catalog_data: dict) -> None:
    response = api_client.get("/api/v1/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["item_count"] == 4
    assert payload["planned_count"] == 2
    assert payload["completed_count"] == 2
    assert payload["collection_count"] == 1
    assert payload["category_count"] == 2


def test_categories_wrapper_and_counts(api_client: TestClient, catalog_data: dict) -> None:
    response = api_client.get("/api/v1/categories")
    assert response.status_code == 200
    payload = response.json()
    assert "categories" in payload
    names = [c["name"] for c in payload["categories"]]
    assert names == ["영화", "빈카테고리"]
    movie = payload["categories"][0]
    assert movie["item_count"] == 4
    assert movie["planned_count"] == 2
    assert movie["completed_count"] == 2
    assert "color" not in movie
    assert "icon" not in movie
    empty = payload["categories"][1]
    assert empty["item_count"] == 0
    assert empty["planned_count"] == 0
    assert empty["completed_count"] == 0


def test_items_pagination_and_serialization(api_client: TestClient, catalog_data: dict) -> None:
    response = api_client.get("/api/v1/items", params={"page": 1, "page_size": 2})
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 2
    assert payload["total"] == 4
    assert payload["total_pages"] == 2
    assert payload["has_next"] is True
    assert payload["has_previous"] is False
    assert len(payload["items"]) == 2
    rating = payload["items"][0]["rating"]
    assert isinstance(rating, (int, float))
    assert not isinstance(rating, str)


def test_items_page_bounds(api_client: TestClient, catalog_data: dict) -> None:
    assert api_client.get("/api/v1/items", params={"page": 0}).status_code == 422
    assert api_client.get("/api/v1/items", params={"page_size": 0}).status_code == 422
    assert api_client.get("/api/v1/items", params={"page_size": 101}).status_code == 422
    over = api_client.get("/api/v1/items", params={"page": 99, "page_size": 25}).json()
    assert over["items"] == []
    assert over["total"] == 4
    assert over["has_next"] is False


def test_items_search_escape(api_client: TestClient, catalog_data: dict) -> None:
    # Literal percent
    hit = api_client.get("/api/v1/items", params={"search": "100%"}).json()
    assert hit["total"] == 1
    assert hit["items"][0]["title"] == "100%_escape\\test"

    underscore = api_client.get("/api/v1/items", params={"search": "_escape"}).json()
    assert underscore["total"] == 1

    blank = api_client.get("/api/v1/items", params={"search": "   "}).json()
    assert blank["total"] == 4


def test_items_filters(api_client: TestClient, catalog_data: dict) -> None:
    movie_id = str(catalog_data["movie"].id)
    col_id = str(catalog_data["col"].id)

    by_cat = api_client.get("/api/v1/items", params={"category_id": movie_id}).json()
    assert by_cat["total"] == 4

    planned = api_client.get("/api/v1/items", params={"status": "PLANNED"}).json()
    assert planned["total"] == 2

    by_col = api_client.get("/api/v1/items", params={"collection_id": col_id}).json()
    assert by_col["total"] == 1
    assert by_col["items"][0]["collection"]["name"] == "007 시리즈"

    has = api_client.get("/api/v1/items", params={"has_collection": True}).json()
    assert has["total"] == 1
    none = api_client.get("/api/v1/items", params={"has_collection": False}).json()
    assert none["total"] == 3

    missing = api_client.get("/api/v1/items", params={"category_id": str(uuid4())}).json()
    assert missing["total"] == 0
    assert missing["items"] == []

    assert api_client.get("/api/v1/items", params={"category_id": "not-a-uuid"}).status_code == 422

    conflict = api_client.get(
        "/api/v1/items",
        params={"has_collection": False, "collection_id": col_id},
    )
    assert conflict.status_code == 422


def test_items_sort_stable(api_client: TestClient, catalog_data: dict) -> None:
    by_title = api_client.get("/api/v1/items", params={"sort": "title", "order": "asc"}).json()
    titles = [item["title"] for item in by_title["items"]]
    assert titles == sorted(titles)


def test_item_detail(api_client: TestClient, catalog_data: dict) -> None:
    long_item = catalog_data["items"][catalog_data["long_title"]]
    response = api_client.get(f"/api/v1/items/{long_item.id}")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["title"]) == 321
    assert payload["memo"] is None
    assert "poster_path" not in payload
    assert "external_source" not in payload

    with_col = catalog_data["items"]["007 골드핑거"]
    detail = api_client.get(f"/api/v1/items/{with_col.id}").json()
    assert detail["collection"]["name"] == "007 시리즈"
    assert detail["rating"] == 4.5

    assert api_client.get(f"/api/v1/items/{uuid4()}").status_code == 404
    assert api_client.get(f"/api/v1/items/{catalog_data['other_item'].id}").status_code == 404


def test_items_include_all_owned_rows(api_client: TestClient, catalog_data: dict) -> None:
    """Existing owned items are listed; other users remain excluded."""
    response = api_client.get("/api/v1/items", params={"page_size": 100})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 4
    titles = {row["title"] for row in payload["items"]}
    assert "타유저영화" not in titles
    assert catalog_data["long_title"] in titles
    assert "007 골드핑거" in titles


def test_items_no_n_plus_one(api_client: TestClient, catalog_data: dict, db: Session) -> None:
    statements: list[str] = []
    bind = db.get_bind()

    def before_cursor(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        statements.append(str(statement))

    event.listen(bind, "before_cursor_execute", before_cursor)
    try:
        statements.clear()
        response = api_client.get("/api/v1/items", params={"page_size": 25})
        assert response.status_code == 200
        assert len(statements) <= 4
    finally:
        event.remove(bind, "before_cursor_execute", before_cursor)


def test_openapi_includes_read_paths(api_client: TestClient) -> None:
    paths = api_client.get("/openapi.json").json()["paths"]
    assert "/api/v1/summary" in paths
    assert "/api/v1/categories" in paths
    assert "/api/v1/collections" in paths
    assert "/api/v1/collections/{collection_id}" in paths
    assert "/api/v1/items" in paths
    assert "/api/v1/items/{item_id}" in paths
