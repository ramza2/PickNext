"""Item release_year create/update validation and response fields."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.main import create_app
from app.models import Category, CategoryType, Item, ItemStatus, User


@pytest.fixture
def owner(db: Session) -> User:
    user = User(
        email=f"release-year-{uuid4().hex[:8]}@picknext.local",
        display_name="Owner",
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

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: owner
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _category(db: Session, user: User) -> Category:
    row = Category(
        user_id=user.id,
        name="영화",
        category_type=CategoryType.MEDIA,
        sort_order=0,
    )
    db.add(row)
    db.flush()
    return row


def test_create_item_with_release_year(
    api_client: TestClient, db: Session, owner: User
) -> None:
    category = _category(db, owner)
    response = api_client.post(
        "/api/v1/items",
        json={
            "title": "오펜하이머",
            "category_id": str(category.id),
            "release_year": 2023,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["release_year"] == 2023
    assert body["poster_url"] is None
    assert body["backdrop_url"] is None


def test_create_item_without_release_year(
    api_client: TestClient, db: Session, owner: User
) -> None:
    category = _category(db, owner)
    response = api_client.post(
        "/api/v1/items",
        json={"title": "무연도", "category_id": str(category.id)},
    )
    assert response.status_code == 201
    assert response.json()["release_year"] is None


@pytest.mark.parametrize("year", [1000, 9999])
def test_create_item_release_year_bounds_ok(
    api_client: TestClient, db: Session, owner: User, year: int
) -> None:
    category = _category(db, owner)
    response = api_client.post(
        "/api/v1/items",
        json={
            "title": f"year-{year}",
            "category_id": str(category.id),
            "release_year": year,
        },
    )
    assert response.status_code == 201
    assert response.json()["release_year"] == year


@pytest.mark.parametrize("year", [999, 10000, "abc", 2023.5, -1])
def test_create_item_release_year_rejected(
    api_client: TestClient, db: Session, owner: User, year: object
) -> None:
    category = _category(db, owner)
    response = api_client.post(
        "/api/v1/items",
        json={
            "title": "bad-year",
            "category_id": str(category.id),
            "release_year": year,
        },
    )
    assert response.status_code == 422


def test_update_release_year_change_and_clear(
    api_client: TestClient, db: Session, owner: User
) -> None:
    category = _category(db, owner)
    create = api_client.post(
        "/api/v1/items",
        json={
            "title": "연도수정",
            "category_id": str(category.id),
            "release_year": 2023,
        },
    )
    assert create.status_code == 201
    item_id = create.json()["id"]

    patched = api_client.patch(
        f"/api/v1/items/{item_id}", json={"release_year": 2024}
    )
    assert patched.status_code == 200
    assert patched.json()["release_year"] == 2024

    cleared = api_client.patch(
        f"/api/v1/items/{item_id}", json={"release_year": None}
    )
    assert cleared.status_code == 200
    assert cleared.json()["release_year"] is None

    again = api_client.patch(
        f"/api/v1/items/{item_id}", json={"memo": "keep-year"}
    )
    assert again.status_code == 200
    assert again.json()["release_year"] is None
    assert again.json()["memo"] == "keep-year"

    set_year = api_client.patch(
        f"/api/v1/items/{item_id}", json={"release_year": 2019}
    )
    assert set_year.status_code == 200
    omitted = api_client.patch(
        f"/api/v1/items/{item_id}", json={"title": "연도유지"}
    )
    assert omitted.status_code == 200
    assert omitted.json()["release_year"] == 2019
    assert omitted.json()["title"] == "연도유지"


def test_legacy_item_response_null_media_fields(
    api_client: TestClient, db: Session, owner: User
) -> None:
    category = _category(db, owner)
    item = Item(
        user_id=owner.id,
        category_id=category.id,
        title="레거시",
        status=ItemStatus.PLANNED,
        rating=Decimal("0.0"),
    )
    db.add(item)
    db.flush()

    response = api_client.get(f"/api/v1/items/{item.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["release_year"] is None
    assert body["poster_path"] is None
    assert body["backdrop_path"] is None
    assert body["poster_url"] is None
    assert body["backdrop_url"] is None
