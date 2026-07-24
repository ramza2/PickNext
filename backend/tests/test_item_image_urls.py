"""Item poster_url / backdrop_url serialization (no TMDB network)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.integrations.tmdb.images import (
    build_tmdb_backdrop_url,
    build_tmdb_poster_url,
    item_backdrop_url,
    item_poster_url,
)
from app.main import create_app
from app.models import Category, CategoryType, Item, ItemStatus, User


def test_build_tmdb_urls_pure() -> None:
    assert build_tmdb_poster_url("/abc.jpg") == (
        "https://image.tmdb.org/t/p/w500/abc.jpg"
    )
    assert build_tmdb_backdrop_url("/xyz.jpg") == (
        "https://image.tmdb.org/t/p/w780/xyz.jpg"
    )
    assert build_tmdb_poster_url(None) is None
    assert build_tmdb_poster_url("") is None
    assert build_tmdb_poster_url("https://evil.example/x.jpg") is None


def test_item_urls_only_for_tmdb_source() -> None:
    assert item_poster_url(external_source="tmdb", poster_path="/p.jpg") == (
        "https://image.tmdb.org/t/p/w500/p.jpg"
    )
    assert item_backdrop_url(external_source="tmdb", backdrop_path="/b.jpg") == (
        "https://image.tmdb.org/t/p/w780/b.jpg"
    )
    assert item_poster_url(external_source=None, poster_path="/p.jpg") is None
    assert item_poster_url(external_source="other", poster_path="/p.jpg") is None


def test_item_list_returns_urls_without_configuration_calls(
    db: Session, monkeypatch
) -> None:
    owner = User(
        email=f"img-url-{uuid4().hex[:8]}@picknext.local",
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

    for index in range(3):
        db.add(
            Item(
                user_id=owner.id,
                category_id=category.id,
                title=f"TMDB {index}",
                status=ItemStatus.PLANNED,
                rating=Decimal("0.0"),
                external_source="tmdb",
                external_id=str(1000 + index),
                external_media_type="movie",
                poster_path=f"/p{index}.jpg",
                backdrop_path=f"/b{index}.jpg",
                release_year=2020 + index,
            )
        )
    db.add(
        Item(
            user_id=owner.id,
            category_id=category.id,
            title="Legacy",
            status=ItemStatus.PLANNED,
            rating=Decimal("0.0"),
            poster_path="/should-not-become-url.jpg",
        )
    )
    db.flush()

    config_get = MagicMock()
    monkeypatch.setattr(
        "app.integrations.tmdb.client.TmdbClient.get_configuration",
        config_get,
        raising=False,
    )

    app = create_app()

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: owner

    with TestClient(app) as client:
        response = client.get("/api/v1/items", params={"page_size": 25})
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert config_get.call_count == 0

    items = response.json()["items"]
    tmdb_rows = [row for row in items if row["external_source"] == "tmdb"]
    assert len(tmdb_rows) >= 3
    for row in tmdb_rows:
        assert row["poster_url"].startswith("https://image.tmdb.org/t/p/w500/")
        assert row["backdrop_url"].startswith("https://image.tmdb.org/t/p/w780/")
        assert row["poster_url"].startswith("https://")

    legacy = next(row for row in items if row["title"] == "Legacy")
    assert legacy["poster_url"] is None
    assert legacy["backdrop_url"] is None
    assert legacy["release_year"] is None
