"""REC-1: random recommendation and recommendation history tests."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
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
    RecommendationHistory,
    RecommendationHistoryItem,
    StatusFilter,
    User,
)
from app.services import recommendation_history_service, recommendation_service
from app.services.recommendation_service import RecommendationCandidate


@pytest.fixture
def owner(db: Session) -> User:
    user = User(
        email=f"rec-owner-{uuid4().hex[:8]}@picknext.local",
        display_name="Rec Owner",
        password_hash="hash",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def other_user(db: Session) -> User:
    user = User(
        email=f"rec-other-{uuid4().hex[:8]}@picknext.local",
        display_name="Rec Other",
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


class FixedIndexProvider:
    def __init__(self, index: int) -> None:
        self.index = index

    def next_index(self, upper_bound: int) -> int:
        assert 0 <= self.index < upper_bound
        return self.index


def _category(db: Session, user: User, name: str = "영화", sort_order: int = 0) -> Category:
    category = Category(
        user_id=user.id,
        name=name,
        category_type=CategoryType.MEDIA,
        sort_order=sort_order,
    )
    db.add(category)
    db.flush()
    return category


def _collection(db: Session, user: User, name: str) -> Collection:
    collection = Collection(user_id=user.id, name=name)
    db.add(collection)
    db.flush()
    return collection


def _item(
    db: Session,
    user: User,
    category: Category,
    *,
    title: str,
    status: ItemStatus = ItemStatus.PLANNED,
    collection: Collection | None = None,
    rating: str = "0.0",
    release_year: int | None = None,
) -> Item:
    item = Item(
        user_id=user.id,
        category_id=category.id,
        collection_id=collection.id if collection else None,
        title=title,
        status=status,
        rating=Decimal(rating),
        release_year=release_year,
    )
    db.add(item)
    db.flush()
    return item


def test_candidate_units_item_and_collection(
    db: Session,
    owner: User,
) -> None:
    cat = _category(db, owner)
    col = _collection(db, owner, "007")
    a = _item(db, owner, cat, title="A")
    b = _item(db, owner, cat, title="B")
    _item(db, owner, cat, title="C1", collection=col)
    _item(db, owner, cat, title="C2", collection=col)
    _item(db, owner, cat, title="C3", collection=col)

    other_cat = _category(db, owner, "드라마", sort_order=1)
    _item(db, owner, other_cat, title="OtherCat")

    candidates = recommendation_service.list_eligible_candidates(
        db, owner, cat.id, StatusFilter.PLANNED
    )
    assert len(candidates) == 3
    ids = {(c.candidate_type, c.candidate_id) for c in candidates}
    assert ("ITEM", a.id) in ids
    assert ("ITEM", b.id) in ids
    assert ("COLLECTION", col.id) in ids


def test_status_filters_and_user_isolation(
    db: Session,
    owner: User,
    other_user: User,
) -> None:
    cat_a = _category(db, owner)
    cat_b = _category(db, other_user)
    _item(db, owner, cat_a, title="Planned", status=ItemStatus.PLANNED)
    _item(db, owner, cat_a, title="Done", status=ItemStatus.COMPLETED)
    _item(db, other_user, cat_b, title="OtherUser")

    planned = recommendation_service.list_eligible_candidates(
        db, owner, cat_a.id, StatusFilter.PLANNED
    )
    completed = recommendation_service.list_eligible_candidates(
        db, owner, cat_a.id, StatusFilter.COMPLETED
    )
    all_c = recommendation_service.list_eligible_candidates(
        db, owner, cat_a.id, StatusFilter.ALL
    )
    assert len(planned) == 1
    assert len(completed) == 1
    assert len(all_c) == 2

    other_pool = recommendation_service.list_eligible_candidates(
        db, other_user, cat_b.id, StatusFilter.ALL
    )
    assert len(other_pool) == 1
    assert other_pool[0].candidate_id != planned[0].candidate_id


def test_random_selection_and_empty(
    db: Session,
    owner: User,
    api_client: TestClient,
) -> None:
    cat = _category(db, owner)
    item = _item(db, owner, cat, title="Only")

    result = recommendation_service.get_random_recommendation(
        db,
        owner,
        category_id=cat.id,
        status_filter=StatusFilter.PLANNED,
        random_provider=FixedIndexProvider(0),
    )
    assert result["candidate_type"] == "ITEM"
    assert result["candidate_id"] == item.id
    assert result["eligible_candidate_count"] == 1
    assert len(result["items"]) == 1

    empty_cat = _category(db, owner, "빈", sort_order=2)
    empty = recommendation_service.get_random_recommendation(
        db,
        owner,
        category_id=empty_cat.id,
        status_filter=StatusFilter.ALL,
    )
    assert empty["candidate_type"] is None
    assert empty["items"] == []
    assert empty["eligible_candidate_count"] == 0

    response = api_client.post(
        "/api/v1/recommendations/random",
        json={"category_id": str(empty_cat.id), "status_filter": "ALL"},
    )
    assert response.status_code == 200
    assert response.json()["eligible_candidate_count"] == 0


def test_collection_result_returns_all_items_mixed_category_status(
    db: Session,
    owner: User,
    api_client: TestClient,
) -> None:
    movie = _category(db, owner, "영화", sort_order=0)
    drama = _category(db, owner, "드라마", sort_order=1)
    col = _collection(db, owner, "시리즈")
    first = _item(
        db, owner, drama, title="Ep2", status=ItemStatus.COMPLETED, collection=col
    )
    second = _item(
        db, owner, movie, title="Ep1", status=ItemStatus.PLANNED, collection=col
    )

    # Eligible via movie+PLANNED → one collection candidate
    candidates = recommendation_service.list_eligible_candidates(
        db, owner, movie.id, StatusFilter.PLANNED
    )
    assert candidates == [RecommendationCandidate("COLLECTION", col.id)]

    result = recommendation_service.get_random_recommendation(
        db,
        owner,
        category_id=movie.id,
        status_filter=StatusFilter.PLANNED,
        random_provider=FixedIndexProvider(0),
    )
    assert result["candidate_type"] == "COLLECTION"
    assert len(result["items"]) == 2
    titles = [row["title"] for row in result["items"]]
    # Category.sort_order: movie(0) before drama(1)
    assert titles == ["Ep1", "Ep2"]
    assert {row["category"]["name"] for row in result["items"]} == {"영화", "드라마"}
    assert {row["status"] for row in result["items"]} == {"PLANNED", "COMPLETED"}
    assert first.id and second.id

    response = api_client.post(
        "/api/v1/recommendations/random",
        json={"category_id": str(movie.id), "status_filter": "PLANNED"},
    )
    assert response.status_code == 200
    assert response.json()["candidate_type"] == "COLLECTION"
    assert len(response.json()["items"]) == 2


def test_history_does_not_affect_candidates_and_repeat_pick(
    db: Session,
    owner: User,
    other_user: User,
) -> None:
    cat = _category(db, owner)
    items = [_item(db, owner, cat, title=f"I{i}") for i in range(3)]
    col = _collection(db, owner, "Col")
    _item(db, owner, cat, title="ColItem", collection=col)

    before = recommendation_service.list_eligible_candidates(
        db, owner, cat.id, StatusFilter.ALL
    )
    assert len(before) == 4

    # Unsaved recommend does not change pool
    first = recommendation_service.get_random_recommendation(
        db,
        owner,
        category_id=cat.id,
        status_filter=StatusFilter.ALL,
        random_provider=FixedIndexProvider(0),
    )
    assert first["candidate_id"] == before[0].candidate_id
    assert len(
        recommendation_service.list_eligible_candidates(
            db, owner, cat.id, StatusFilter.ALL
        )
    ) == 4

    # Same stub index → same candidate again (independent random)
    second = recommendation_service.get_random_recommendation(
        db,
        owner,
        category_id=cat.id,
        status_filter=StatusFilter.ALL,
        random_provider=FixedIndexProvider(0),
    )
    assert second["candidate_id"] == first["candidate_id"]
    assert second["candidate_type"] == first["candidate_type"]

    # Save item + collection histories — pool unchanged
    recommendation_history_service.create_recommendation_history(
        db,
        owner,
        category_id=cat.id,
        status_filter=StatusFilter.ALL,
        candidate_type="ITEM",
        candidate_id=items[0].id,
        commit=False,
    )
    db.flush()
    recommendation_history_service.create_recommendation_history(
        db,
        owner,
        category_id=cat.id,
        status_filter=StatusFilter.ALL,
        candidate_type="COLLECTION",
        candidate_id=col.id,
        commit=False,
    )
    db.flush()

    after_history = recommendation_service.list_eligible_candidates(
        db, owner, cat.id, StatusFilter.ALL
    )
    assert len(after_history) == 4
    after_ids = {(c.candidate_type, c.candidate_id) for c in after_history}
    assert ("ITEM", items[0].id) in after_ids
    assert ("COLLECTION", col.id) in after_ids

    # Saved item can be recommended again
    item_index = next(
        i
        for i, c in enumerate(after_history)
        if c.candidate_type == "ITEM" and c.candidate_id == items[0].id
    )
    again_item = recommendation_service.get_random_recommendation(
        db,
        owner,
        category_id=cat.id,
        status_filter=StatusFilter.ALL,
        random_provider=FixedIndexProvider(item_index),
    )
    assert again_item["candidate_type"] == "ITEM"
    assert again_item["candidate_id"] == items[0].id

    # Saved collection can be recommended again
    col_index = next(
        i
        for i, c in enumerate(after_history)
        if c.candidate_type == "COLLECTION" and c.candidate_id == col.id
    )
    again_col = recommendation_service.get_random_recommendation(
        db,
        owner,
        category_id=cat.id,
        status_filter=StatusFilter.ALL,
        random_provider=FixedIndexProvider(col_index),
    )
    assert again_col["candidate_type"] == "COLLECTION"
    assert again_col["candidate_id"] == col.id

    # Other user history does not change owner pool
    other_cat = _category(db, other_user)
    other_item = _item(db, other_user, other_cat, title="Other")
    recommendation_history_service.create_recommendation_history(
        db,
        other_user,
        category_id=other_cat.id,
        status_filter=StatusFilter.ALL,
        candidate_type="ITEM",
        candidate_id=other_item.id,
        commit=False,
    )
    still = recommendation_service.list_eligible_candidates(
        db, owner, cat.id, StatusFilter.ALL
    )
    assert len(still) == 4


def test_history_save_list_detail_delete(
    db: Session,
    owner: User,
    other_user: User,
    api_client: TestClient,
) -> None:
    cat = _category(db, owner)
    item = _item(db, owner, cat, title="Solo", release_year=2020)
    col = _collection(db, owner, "Pack")
    _item(db, owner, cat, title="P1", collection=col)
    _item(db, owner, cat, title="P2", collection=col)

    before = db.scalar(select(func.count()).select_from(RecommendationHistory)) or 0

    recommend = api_client.post(
        "/api/v1/recommendations/random",
        json={"category_id": str(cat.id), "status_filter": "ALL"},
    )
    assert recommend.status_code == 200
    assert (
        db.scalar(select(func.count()).select_from(RecommendationHistory)) or 0
    ) == before

    created_item = api_client.post(
        "/api/v1/recommendation-history",
        json={
            "category_id": str(cat.id),
            "status_filter": "ALL",
            "candidate_type": "ITEM",
            "candidate_id": str(item.id),
        },
    )
    assert created_item.status_code == 201
    body = created_item.json()
    assert body["candidate_type"] == "ITEM"
    assert len(body["items"]) == 1
    assert body["items"][0]["title_snapshot"] == "Solo"
    assert body["items"][0]["status_at_selection"] == "PLANNED"

    created_col = api_client.post(
        "/api/v1/recommendation-history",
        json={
            "category_id": str(cat.id),
            "status_filter": "ALL",
            "candidate_type": "COLLECTION",
            "candidate_id": str(col.id),
        },
    )
    assert created_col.status_code == 201
    assert len(created_col.json()["items"]) == 2
    assert [row["sort_order"] for row in created_col.json()["items"]] == [0, 1]

    listed = api_client.get("/api/v1/recommendation-history", params={"page": 1, "page_size": 10})
    assert listed.status_code == 200
    assert listed.json()["total"] == 2
    assert listed.json()["items"][0]["id"] == created_col.json()["id"]

    detail = api_client.get(
        f"/api/v1/recommendation-history/{created_item.json()['id']}"
    )
    assert detail.status_code == 200
    assert detail.json()["items"][0]["current"]["release_year"] == 2020

    # Same candidate again allowed
    again = api_client.post(
        "/api/v1/recommendation-history",
        json={
            "category_id": str(cat.id),
            "status_filter": "ALL",
            "candidate_type": "ITEM",
            "candidate_id": str(item.id),
        },
    )
    assert again.status_code == 201

    deleted = api_client.delete(
        f"/api/v1/recommendation-history/{created_item.json()['id']}"
    )
    assert deleted.status_code == 204
    assert (
        api_client.get(
            f"/api/v1/recommendation-history/{created_item.json()['id']}"
        ).status_code
        == 404
    )

    # Isolation: other user override
    app = create_app()

    def _override_db():
        yield db

    def _override_other():
        return other_user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_other
    with TestClient(app) as other_client:
        assert (
            other_client.get(
                f"/api/v1/recommendation-history/{created_col.json()['id']}"
            ).status_code
            == 404
        )
        assert (
            other_client.delete(
                f"/api/v1/recommendation-history/{created_col.json()['id']}"
            ).status_code
            == 404
        )
        assert other_client.get("/api/v1/recommendation-history").json()["total"] == 0
        wipe = other_client.delete("/api/v1/recommendation-history")
        assert wipe.status_code == 200
        assert wipe.json()["deleted_count"] == 0

    remaining = api_client.get("/api/v1/recommendation-history").json()["total"]
    assert remaining >= 1

    wiped = api_client.delete("/api/v1/recommendation-history")
    assert wiped.status_code == 200
    assert wiped.json()["deleted_count"] == remaining
    assert api_client.get("/api/v1/recommendation-history").json()["total"] == 0


def test_unauthorized_recommendation_endpoints(client: TestClient) -> None:
    assert (
        client.post(
            "/api/v1/recommendations/random",
            json={
                "category_id": str(uuid4()),
                "status_filter": "PLANNED",
            },
        ).status_code
        == 401
    )
    assert client.get("/api/v1/recommendation-history").status_code == 401
    assert (
        client.post(
            "/api/v1/recommendation-history",
            json={
                "category_id": str(uuid4()),
                "status_filter": "PLANNED",
                "candidate_type": "ITEM",
                "candidate_id": str(uuid4()),
            },
        ).status_code
        == 401
    )


def test_other_user_category_404(
    db: Session,
    owner: User,
    other_user: User,
    api_client: TestClient,
) -> None:
    other_cat = _category(db, other_user)
    response = api_client.post(
        "/api/v1/recommendations/random",
        json={"category_id": str(other_cat.id), "status_filter": "ALL"},
    )
    assert response.status_code == 404


def test_item_hard_delete_removes_history_parent(
    db: Session,
    owner: User,
) -> None:
    from app.services import catalog

    cat = _category(db, owner)
    col = _collection(db, owner, "Keep")
    keep = _item(db, owner, cat, title="Keep", collection=col)
    doomed = _item(db, owner, cat, title="Doomed", collection=col)

    history = recommendation_history_service.create_recommendation_history(
        db,
        owner,
        category_id=cat.id,
        status_filter=StatusFilter.ALL,
        candidate_type="COLLECTION",
        candidate_id=col.id,
        commit=False,
    )
    history_id = history.id
    db.flush()

    catalog.delete_item(db, owner, doomed.id, commit=False)
    db.flush()

    assert db.get(RecommendationHistory, history_id) is None
    assert (
        db.scalar(
            select(func.count())
            .select_from(RecommendationHistoryItem)
            .where(RecommendationHistoryItem.recommendation_history_id == history_id)
        )
        or 0
    ) == 0
    assert db.get(Item, keep.id) is not None
    assert db.get(Item, doomed.id) is None
