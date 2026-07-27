"""Cross-user data isolation tests with real session cookies (AUTH-1)."""

from __future__ import annotations

from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import get_db
from app.main import create_app
from app.models import Category, ItemStatus, User
from app.services.seed import ensure_default_categories_for_user

TEST_PASSWORD = "test-password-ok"


def _unique_login_id(prefix: str) -> str:
    return f"{prefix}{uuid4().hex[:6]}"


def _create_user(db: Session, *, prefix: str) -> tuple[str, User]:
    login_id = _unique_login_id(prefix)
    email = f"{login_id}@example.com"
    user = User(
        email=email,
        display_name=login_id,
        login_id=login_id,
        password_hash=hash_password(TEST_PASSWORD),
        is_active=True,
    )
    db.add(user)
    db.flush()
    ensure_default_categories_for_user(db, user)
    db.flush()
    return login_id, user


@pytest.fixture
def isolated_clients(db: Session) -> Generator[tuple[TestClient, TestClient, User, User], None, None]:
    app = create_app()

    def _override_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _override_db

    login_a, user_a = _create_user(db, prefix="a")
    login_b, user_b = _create_user(db, prefix="b")

    client_a = TestClient(app)
    client_b = TestClient(app)

    for client, login_id in ((client_a, login_a), (client_b, login_b)):
        response = client.post(
            "/api/v1/auth/login",
            json={"login_id": login_id, "password": TEST_PASSWORD, "remember_me": False},
        )
        assert response.status_code == 200

    yield client_a, client_b, user_a, user_b
    app.dependency_overrides.clear()


def _first_category(db: Session, user: User) -> Category:
    category = db.scalar(select(Category).where(Category.user_id == user.id))
    assert category is not None
    return category


def test_user_b_cannot_see_user_a_item(
    isolated_clients: tuple[TestClient, TestClient, User, User],
    db: Session,
) -> None:
    client_a, client_b, user_a, user_b = isolated_clients
    category = _first_category(db, user_a)

    created = client_a.post(
        "/api/v1/items",
        json={
            "category_id": str(category.id),
            "title": "User A Secret Item",
            "status": ItemStatus.PLANNED.value,
            "rating": "0.0",
        },
    )
    assert created.status_code == 201
    item_id = created.json()["id"]

    listed = client_b.get("/api/v1/items", params={"page_size": 100})
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()["items"]}
    assert item_id not in ids

    detail = client_b.get(f"/api/v1/items/{item_id}")
    assert detail.status_code == 404

    patched = client_b.patch(
        f"/api/v1/items/{item_id}",
        json={"title": "Hijacked"},
    )
    assert patched.status_code == 404

    deleted = client_b.delete(f"/api/v1/items/{item_id}")
    assert deleted.status_code == 404

    still_there = client_a.get(f"/api/v1/items/{item_id}")
    assert still_there.status_code == 200
    assert still_there.json()["title"] == "User A Secret Item"


def test_summary_and_catalog_counts_differ(
    isolated_clients: tuple[TestClient, TestClient, User, User],
    db: Session,
) -> None:
    client_a, client_b, user_a, _user_b = isolated_clients
    category = _first_category(db, user_a)

    created = client_a.post(
        "/api/v1/items",
        json={
            "category_id": str(category.id),
            "title": "Only A Item",
            "status": ItemStatus.PLANNED.value,
            "rating": "0.0",
        },
    )
    assert created.status_code == 201

    summary_a = client_a.get("/api/v1/summary").json()
    summary_b = client_b.get("/api/v1/summary").json()
    assert summary_a["item_count"] == 1
    assert summary_b["item_count"] == 0

    categories_a = client_a.get("/api/v1/categories").json()["categories"]
    categories_b = client_b.get("/api/v1/categories").json()["categories"]
    assert len(categories_a) > 0
    assert len(categories_b) > 0
    assert max(row["item_count"] for row in categories_a) >= 1
    assert all(row["item_count"] == 0 for row in categories_b)


def test_collections_isolated(
    isolated_clients: tuple[TestClient, TestClient, User, User],
) -> None:
    client_a, client_b, _user_a, _user_b = isolated_clients

    created = client_a.post("/api/v1/collections", json={"name": "A Only Collection"})
    assert created.status_code == 201
    collection_id = created.json()["id"]

    listed = client_b.get("/api/v1/collections", params={"page_size": 100})
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()["collections"]}
    assert collection_id not in ids

    detail = client_b.get(f"/api/v1/collections/{collection_id}")
    assert detail.status_code == 404
