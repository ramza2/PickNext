"""Item synopsis (TMDB overview) persistence tests."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.main import create_app
from app.models import Category, CategoryType, Item, ItemStatus, User
from app.services.tmdb_service import normalize_overview_text


def test_normalize_overview_text() -> None:
    assert normalize_overview_text(None) is None
    assert normalize_overview_text("") is None
    assert normalize_overview_text("   ") is None
    assert normalize_overview_text("  한 소년  ") == "한 소년"
    assert normalize_overview_text("첫줄\n둘째줄") == "첫줄\n둘째줄"
    assert normalize_overview_text(123) is None


def test_manual_create_and_clear_synopsis(db: Session) -> None:
    owner = User(
        email=f"syn-{uuid4().hex[:8]}@picknext.local",
        display_name="Owner",
        password_hash="hash",
        is_active=True,
    )
    db.add(owner)
    db.flush()
    category = Category(
        user_id=owner.id,
        name="영화",
        category_type=CategoryType.MEDIA,
        sort_order=0,
    )
    db.add(category)
    db.flush()

    app = create_app()

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: owner
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/items",
            json={
                "title": "줄거리있음",
                "category_id": str(category.id),
                "synopsis": "  한 소년이 모험을 시작한다.  ",
            },
        )
        assert created.status_code == 201
        body = created.json()
        assert body["synopsis"] == "한 소년이 모험을 시작한다."

        item_id = body["id"]
        cleared = client.patch(
            f"/api/v1/items/{item_id}",
            json={"synopsis": None},
        )
        assert cleared.status_code == 200
        assert cleared.json()["synopsis"] is None

        multiline = client.patch(
            f"/api/v1/items/{item_id}",
            json={"synopsis": "첫줄\n\n둘째줄"},
        )
        assert multiline.status_code == 200
        assert multiline.json()["synopsis"] == "첫줄\n\n둘째줄"

        long_text = "가" * 5000
        long_res = client.patch(
            f"/api/v1/items/{item_id}",
            json={"synopsis": long_text},
        )
        assert long_res.status_code == 200
        assert long_res.json()["synopsis"] == long_text

    app.dependency_overrides.clear()


def test_legacy_item_synopsis_null(db: Session) -> None:
    owner = User(
        email=f"syn-leg-{uuid4().hex[:8]}@picknext.local",
        display_name="Owner",
        password_hash="hash",
        is_active=True,
    )
    db.add(owner)
    db.flush()
    category = Category(
        user_id=owner.id,
        name="영화",
        category_type=CategoryType.MEDIA,
        sort_order=0,
    )
    db.add(category)
    db.flush()
    item = Item(
        user_id=owner.id,
        category_id=category.id,
        title="레거시",
        status=ItemStatus.PLANNED,
        rating=Decimal("0.0"),
    )
    db.add(item)
    db.flush()

    app = create_app()

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: owner
    with TestClient(app) as client:
        response = client.get(f"/api/v1/items/{item.id}")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["synopsis"] is None
