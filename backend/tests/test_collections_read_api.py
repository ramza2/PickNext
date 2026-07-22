"""Tests for Collection read APIs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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


def _item(
    *,
    user_id,
    category_id,
    title: str,
    status: ItemStatus,
    collection_id=None,
    deleted_at=None,
) -> Item:
    return Item(
        user_id=user_id,
        category_id=category_id,
        collection_id=collection_id,
        title=title,
        status=status,
        rating=Decimal("0.0"),
        deleted_at=deleted_at,
    )


@pytest.fixture
def owner(db: Session) -> User:
    user = User(
        email=f"col-owner-{uuid4().hex[:8]}@picknext.local",
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
        email=f"col-other-{uuid4().hex[:8]}@picknext.local",
        display_name="Other",
        password_hash="hash",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def collection_data(db: Session, owner: User, other_user: User) -> dict:
    anime = Category(
        user_id=owner.id,
        name="애니메이션",
        category_type=CategoryType.MEDIA,
        sort_order=1,
    )
    anime_movie = Category(
        user_id=owner.id,
        name="애니 영화",
        category_type=CategoryType.MEDIA,
        sort_order=2,
    )
    movie = Category(
        user_id=owner.id,
        name="영화",
        category_type=CategoryType.MEDIA,
        sort_order=3,
    )
    other_cat = Category(
        user_id=other_user.id,
        name="영화",
        category_type=CategoryType.MEDIA,
        sort_order=1,
    )
    db.add_all([anime, anime_movie, movie, other_cat])
    db.flush()

    now = datetime.now(timezone.utc)
    empty = Collection(user_id=owner.id, name="빈컬렉션")
    bond = Collection(user_id=owner.id, name="007 시리즈")
    mixed = Collection(user_id=owner.id, name="드래곤볼")
    planned_only = Collection(user_id=owner.id, name="예정만")
    completed_only = Collection(user_id=owner.id, name="완료만")
    compound = Collection(user_id=owner.id, name="복합필터대상")
    escape_col = Collection(user_id=owner.id, name="100%_escape\\series")
    soft_empty = Collection(user_id=owner.id, name="삭제후빈컬렉션")
    other_col = Collection(user_id=other_user.id, name="타유저컬렉션")
    db.add_all(
        [
            empty,
            bond,
            mixed,
            planned_only,
            completed_only,
            compound,
            escape_col,
            soft_empty,
            other_col,
        ]
    )
    db.flush()

    # Distinct updated_at for stable sort checks
    empty.updated_at = now - timedelta(days=8)
    empty.created_at = now - timedelta(days=8)
    bond.updated_at = now - timedelta(days=1)
    bond.created_at = now - timedelta(days=7)
    mixed.updated_at = now - timedelta(hours=1)
    mixed.created_at = now - timedelta(days=6)
    planned_only.updated_at = now - timedelta(days=3)
    planned_only.created_at = now - timedelta(days=5)
    completed_only.updated_at = now - timedelta(days=2)
    completed_only.created_at = now - timedelta(days=4)
    compound.updated_at = now - timedelta(days=4)
    compound.created_at = now - timedelta(days=3)
    escape_col.updated_at = now - timedelta(days=5)
    escape_col.created_at = now - timedelta(days=2)
    soft_empty.updated_at = now - timedelta(days=6)
    soft_empty.created_at = now - timedelta(days=1)

    items = [
        _item(
            user_id=owner.id,
            category_id=movie.id,
            collection_id=bond.id,
            title="007 골드핑거",
            status=ItemStatus.COMPLETED,
        ),
        _item(
            user_id=owner.id,
            category_id=movie.id,
            collection_id=bond.id,
            title="007 카지노 로얄",
            status=ItemStatus.PLANNED,
        ),
        _item(
            user_id=owner.id,
            category_id=anime.id,
            collection_id=mixed.id,
            title="드래곤볼 Z",
            status=ItemStatus.COMPLETED,
        ),
        _item(
            user_id=owner.id,
            category_id=anime_movie.id,
            collection_id=mixed.id,
            title="드래곤볼 극장판",
            status=ItemStatus.PLANNED,
        ),
        _item(
            user_id=owner.id,
            category_id=movie.id,
            collection_id=mixed.id,
            title="드래곤볼 실사",
            status=ItemStatus.PLANNED,
        ),
        _item(
            user_id=owner.id,
            category_id=movie.id,
            collection_id=planned_only.id,
            title="예정1",
            status=ItemStatus.PLANNED,
        ),
        _item(
            user_id=owner.id,
            category_id=movie.id,
            collection_id=planned_only.id,
            title="예정2",
            status=ItemStatus.PLANNED,
        ),
        _item(
            user_id=owner.id,
            category_id=movie.id,
            collection_id=completed_only.id,
            title="완료1",
            status=ItemStatus.COMPLETED,
        ),
        # compound: movie COMPLETED + anime_movie PLANNED (no movie+PLANNED)
        _item(
            user_id=owner.id,
            category_id=movie.id,
            collection_id=compound.id,
            title="영화완료",
            status=ItemStatus.COMPLETED,
        ),
        _item(
            user_id=owner.id,
            category_id=anime_movie.id,
            collection_id=compound.id,
            title="애니영화예정",
            status=ItemStatus.PLANNED,
        ),
        _item(
            user_id=owner.id,
            category_id=movie.id,
            collection_id=escape_col.id,
            title="다른제목만매칭용",
            status=ItemStatus.PLANNED,
        ),
        _item(
            user_id=owner.id,
            category_id=movie.id,
            collection_id=soft_empty.id,
            title="삭제된소속",
            status=ItemStatus.PLANNED,
            deleted_at=now,
        ),
        # Soft-deleted item must not affect bond filters/counts
        _item(
            user_id=owner.id,
            category_id=anime.id,
            collection_id=bond.id,
            title="삭제된007애니",
            status=ItemStatus.COMPLETED,
            deleted_at=now,
        ),
        # Standalone item whose title looks like a collection name
        _item(
            user_id=owner.id,
            category_id=movie.id,
            collection_id=None,
            title="007 시리즈",
            status=ItemStatus.PLANNED,
        ),
        _item(
            user_id=other_user.id,
            category_id=other_cat.id,
            collection_id=other_col.id,
            title="타유저항목",
            status=ItemStatus.PLANNED,
        ),
    ]
    db.add_all(items)
    db.flush()

    return {
        "owner": owner,
        "other_user": other_user,
        "anime": anime,
        "anime_movie": anime_movie,
        "movie": movie,
        "empty": empty,
        "bond": bond,
        "mixed": mixed,
        "planned_only": planned_only,
        "completed_only": completed_only,
        "compound": compound,
        "escape_col": escape_col,
        "soft_empty": soft_empty,
        "other_col": other_col,
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


def _by_name(payload: dict, name: str) -> dict:
    for row in payload["collections"]:
        if row["name"] == name:
            return row
    raise AssertionError(f"collection not found: {name}")


def test_collections_user_scope(api_client: TestClient, collection_data: dict) -> None:
    payload = api_client.get("/api/v1/collections", params={"page_size": 100}).json()
    names = {row["name"] for row in payload["collections"]}
    assert "타유저컬렉션" not in names
    assert payload["total"] == 8
    assert "빈컬렉션" in names


def test_collection_detail_access(
    api_client: TestClient, collection_data: dict
) -> None:
    bond = collection_data["bond"]
    detail = api_client.get(f"/api/v1/collections/{bond.id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == str(bond.id)
    assert body["name"] == "007 시리즈"
    assert "completion_rate" not in body
    assert "avg_rating" not in body
    assert "items" not in body

    assert api_client.get(f"/api/v1/collections/{uuid4()}").status_code == 404
    assert (
        api_client.get(f"/api/v1/collections/{collection_data['other_col'].id}").status_code
        == 404
    )
    assert api_client.get("/api/v1/collections/not-a-uuid").status_code == 422


def test_list_and_detail_same_schema(
    api_client: TestClient, collection_data: dict
) -> None:
    listing = api_client.get(
        "/api/v1/collections", params={"search": "007 시리즈"}
    ).json()
    assert listing["total"] == 1
    listed = listing["collections"][0]
    detail = api_client.get(f"/api/v1/collections/{listed['id']}").json()
    assert set(listed.keys()) == set(detail.keys())
    assert listed == detail
    assert "created_at" in detail and "updated_at" in detail


def test_empty_collection(api_client: TestClient, collection_data: dict) -> None:
    empty_id = collection_data["empty"].id
    listed = api_client.get("/api/v1/collections", params={"page_size": 100}).json()
    empty = _by_name(listed, "빈컬렉션")
    assert empty["item_count"] == 0
    assert empty["planned_count"] == 0
    assert empty["completed_count"] == 0
    assert empty["categories"] == []

    detail = api_client.get(f"/api/v1/collections/{empty_id}").json()
    assert detail["item_count"] == 0
    assert detail["categories"] == []

    movie_id = str(collection_data["movie"].id)
    by_cat = api_client.get(
        "/api/v1/collections", params={"category_id": movie_id, "page_size": 100}
    ).json()
    assert all(row["name"] != "빈컬렉션" for row in by_cat["collections"])

    by_status = api_client.get(
        "/api/v1/collections", params={"status": "PLANNED", "page_size": 100}
    ).json()
    assert all(row["name"] != "빈컬렉션" for row in by_status["collections"])


def test_soft_delete_excluded(api_client: TestClient, collection_data: dict) -> None:
    bond = api_client.get(f"/api/v1/collections/{collection_data['bond'].id}").json()
    assert bond["item_count"] == 2
    assert bond["planned_count"] == 1
    assert bond["completed_count"] == 1
    assert [c["name"] for c in bond["categories"]] == ["영화"]
    assert bond["categories"][0]["item_count"] == 2

    soft = api_client.get(
        f"/api/v1/collections/{collection_data['soft_empty'].id}"
    ).json()
    assert soft["item_count"] == 0
    assert soft["categories"] == []

    anime_id = str(collection_data["anime"].id)
    # Deleted anime item on bond must not match anime filter
    by_anime = api_client.get(
        "/api/v1/collections", params={"category_id": anime_id, "page_size": 100}
    ).json()
    names = {row["name"] for row in by_anime["collections"]}
    assert "007 시리즈" not in names
    assert "드래곤볼" in names


def test_mixed_categories_sorted(api_client: TestClient, collection_data: dict) -> None:
    mixed = api_client.get(f"/api/v1/collections/{collection_data['mixed'].id}").json()
    assert mixed["item_count"] == 3
    assert mixed["planned_count"] == 2
    assert mixed["completed_count"] == 1
    names = [c["name"] for c in mixed["categories"]]
    assert names == ["애니메이션", "애니 영화", "영화"]
    assert sum(c["item_count"] for c in mixed["categories"]) == mixed["item_count"]
    assert [c["item_count"] for c in mixed["categories"]] == [1, 1, 1]


def test_status_filters_keep_full_aggregates(
    api_client: TestClient, collection_data: dict
) -> None:
    planned = api_client.get(
        "/api/v1/collections", params={"status": "PLANNED", "page_size": 100}
    ).json()
    planned_names = {row["name"] for row in planned["collections"]}
    assert "예정만" in planned_names
    assert "007 시리즈" in planned_names
    assert "완료만" not in planned_names
    assert "빈컬렉션" not in planned_names

    bond = _by_name(planned, "007 시리즈")
    assert bond["item_count"] == 2
    assert bond["planned_count"] == 1
    assert bond["completed_count"] == 1

    completed = api_client.get(
        "/api/v1/collections", params={"status": "COMPLETED", "page_size": 100}
    ).json()
    completed_names = {row["name"] for row in completed["collections"]}
    assert "완료만" in completed_names
    assert "예정만" not in completed_names


def test_category_filter_keeps_full_aggregates(
    api_client: TestClient, collection_data: dict
) -> None:
    movie_id = str(collection_data["movie"].id)
    payload = api_client.get(
        "/api/v1/collections", params={"category_id": movie_id, "page_size": 100}
    ).json()
    mixed = _by_name(payload, "드래곤볼")
    assert mixed["item_count"] == 3
    assert [c["name"] for c in mixed["categories"]] == ["애니메이션", "애니 영화", "영화"]

    missing = api_client.get(
        "/api/v1/collections", params={"category_id": str(uuid4())}
    ).json()
    assert missing["total"] == 0
    assert missing["collections"] == []


def test_compound_filter_same_item(
    api_client: TestClient, collection_data: dict
) -> None:
    movie_id = str(collection_data["movie"].id)
    # movie + PLANNED: compound has movie/COMPLETED and anime_movie/PLANNED → exclude
    excluded = api_client.get(
        "/api/v1/collections",
        params={"category_id": movie_id, "status": "PLANNED", "page_size": 100},
    ).json()
    names = {row["name"] for row in excluded["collections"]}
    assert "복합필터대상" not in names
    assert "드래곤볼" in names  # has movie/PLANNED
    assert "007 시리즈" in names  # has movie/PLANNED

    dragon = _by_name(excluded, "드래곤볼")
    assert dragon["item_count"] == 3
    assert sum(c["item_count"] for c in dragon["categories"]) == 3

    # movie + COMPLETED includes compound
    included = api_client.get(
        "/api/v1/collections",
        params={"category_id": movie_id, "status": "COMPLETED", "page_size": 100},
    ).json()
    assert "복합필터대상" in {row["name"] for row in included["collections"]}
    compound = _by_name(included, "복합필터대상")
    assert compound["item_count"] == 2
    assert compound["planned_count"] == 1
    assert compound["completed_count"] == 1


def test_search_name_only_and_escape(
    api_client: TestClient, collection_data: dict
) -> None:
    by_name = api_client.get("/api/v1/collections", params={"search": "007"}).json()
    assert by_name["total"] == 1
    assert by_name["collections"][0]["name"] == "007 시리즈"

    # Item title equals a collection name must not create extra hits via item search
    # (only the real collection name match)
    assert by_name["total"] == 1

    literal_pct = api_client.get(
        "/api/v1/collections", params={"search": "100%"}
    ).json()
    assert literal_pct["total"] == 1
    assert literal_pct["collections"][0]["name"] == "100%_escape\\series"

    underscore = api_client.get(
        "/api/v1/collections", params={"search": "_escape"}
    ).json()
    assert underscore["total"] == 1

    backslash = api_client.get(
        "/api/v1/collections", params={"search": "escape\\series"}
    ).json()
    assert backslash["total"] == 1

    blank = api_client.get("/api/v1/collections", params={"search": "   "}).json()
    assert blank["total"] == 8

    case_insensitive = api_client.get(
        "/api/v1/collections", params={"search": "007 시리즈"}
    ).json()
    assert case_insensitive["total"] == 1


def test_validation(api_client: TestClient) -> None:
    assert api_client.get("/api/v1/collections", params={"page": 0}).status_code == 422
    assert api_client.get("/api/v1/collections", params={"page_size": 0}).status_code == 422
    assert api_client.get("/api/v1/collections", params={"page_size": 101}).status_code == 422
    assert (
        api_client.get("/api/v1/collections", params={"category_id": "bad"}).status_code
        == 422
    )
    assert api_client.get("/api/v1/collections", params={"status": "ALL"}).status_code == 422
    assert api_client.get("/api/v1/collections", params={"sort": "title"}).status_code == 422
    assert api_client.get("/api/v1/collections", params={"order": "up"}).status_code == 422


def test_pagination(api_client: TestClient, collection_data: dict) -> None:
    page1 = api_client.get(
        "/api/v1/collections", params={"page": 1, "page_size": 3}
    ).json()
    assert page1["page"] == 1
    assert page1["page_size"] == 3
    assert page1["total"] == 8
    assert page1["total_pages"] == 3
    assert page1["has_next"] is True
    assert page1["has_previous"] is False
    assert len(page1["collections"]) == 3

    page2 = api_client.get(
        "/api/v1/collections", params={"page": 2, "page_size": 3}
    ).json()
    assert page2["has_previous"] is True
    assert page2["has_next"] is True

    over = api_client.get(
        "/api/v1/collections", params={"page": 99, "page_size": 25}
    ).json()
    assert over["collections"] == []
    assert over["total"] == 8
    assert over["total_pages"] == 1
    assert over["has_next"] is False

    filtered = api_client.get(
        "/api/v1/collections",
        params={"status": "COMPLETED", "page": 1, "page_size": 100},
    ).json()
    assert filtered["total"] == len(filtered["collections"])


def test_default_sort_updated_at_desc(
    api_client: TestClient, collection_data: dict
) -> None:
    payload = api_client.get(
        "/api/v1/collections", params={"page_size": 100}
    ).json()
    updated = [row["updated_at"] for row in payload["collections"]]
    assert updated == sorted(updated, reverse=True)


def test_all_sorts(api_client: TestClient, collection_data: dict) -> None:
    for sort in ("updated_at", "created_at", "name", "item_count", "completed_count"):
        for order in ("asc", "desc"):
            response = api_client.get(
                "/api/v1/collections",
                params={"sort": sort, "order": order, "page_size": 100},
            )
            assert response.status_code == 200, f"{sort} {order}"
            rows = response.json()["collections"]
            assert len(rows) == 8
            if sort == "name":
                names = [row["name"] for row in rows]
                assert names == sorted(names, reverse=(order == "desc"))
            if sort == "item_count":
                counts = [row["item_count"] for row in rows]
                assert counts == sorted(counts, reverse=(order == "desc"))
            if sort == "completed_count":
                counts = [row["completed_count"] for row in rows]
                assert counts == sorted(counts, reverse=(order == "desc"))


def test_stable_id_tiebreak(api_client: TestClient, db: Session, owner: User) -> None:
    stamp = datetime.now(timezone.utc)
    a = Collection(user_id=owner.id, name="동시A")
    b = Collection(user_id=owner.id, name="동시B")
    db.add_all([a, b])
    db.flush()
    a.updated_at = stamp
    b.updated_at = stamp
    db.flush()

    desc_rows = api_client.get(
        "/api/v1/collections",
        params={"sort": "updated_at", "order": "desc", "page_size": 100},
    ).json()["collections"]
    tied = [row for row in desc_rows if row["name"] in {"동시A", "동시B"}]
    assert [row["id"] for row in tied] == sorted((str(a.id), str(b.id)), reverse=True)


def test_collections_no_n_plus_one(
    api_client: TestClient, collection_data: dict, db: Session
) -> None:
    statements: list[str] = []
    bind = db.get_bind()

    def before_cursor(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        statements.append(str(statement))

    event.listen(bind, "before_cursor_execute", before_cursor)
    try:
        statements.clear()
        response = api_client.get("/api/v1/collections", params={"page_size": 100})
        assert response.status_code == 200
        assert len(response.json()["collections"]) == 8
        assert len(statements) <= 4
    finally:
        event.remove(bind, "before_cursor_execute", before_cursor)


def test_openapi_includes_collection_paths(api_client: TestClient) -> None:
    paths = api_client.get("/openapi.json").json()["paths"]
    assert "/api/v1/collections" in paths
    assert "/api/v1/collections/{collection_id}" in paths
    list_params = {
        p["name"] for p in paths["/api/v1/collections"]["get"]["parameters"]
    }
    assert {
        "search",
        "category_id",
        "status",
        "sort",
        "order",
        "page",
        "page_size",
    } <= list_params
    assert "has_items" not in list_params
