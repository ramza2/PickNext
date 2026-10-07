"""Progress note TEXT storage and >200 character acceptance."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.v1.tmdb import get_tmdb_service
from app.core.config import Settings
from app.db.session import get_db
from app.integrations.tmdb.client import TmdbClient
from app.main import create_app
from app.models import Category, CategoryType, Item, ItemStatus, User
from app.services.tmdb_service import TmdbService


CONFIGURATION = {
    "images": {
        "secure_base_url": "https://image.tmdb.org/t/p/",
        "poster_sizes": ["w92", "w500", "original"],
        "backdrop_sizes": ["w300", "w780", "original"],
        "profile_sizes": ["w45", "w185", "original"],
    }
}


def _movie_details_payload() -> dict:
    return {
        "id": 872585,
        "title": "오펜하이머",
        "original_title": "Oppenheimer",
        "overview": "줄거리",
        "tagline": "tag",
        "original_language": "en",
        "adult": False,
        "status": "Released",
        "release_date": "2023-07-19",
        "runtime": 181,
        "genres": [{"id": 18, "name": "드라마"}],
        "poster_path": "/p.jpg",
        "backdrop_path": "/b.jpg",
        "popularity": 1.0,
        "vote_average": 8.1,
        "vote_count": 10,
        "credits": {"cast": [], "crew": []},
        "external_ids": {"imdb_id": "tt15398776"},
    }


class _Router:
    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/configuration"):
            return httpx.Response(200, json=CONFIGURATION)
        if "/movie/" in path:
            return httpx.Response(200, json=_movie_details_payload())
        return httpx.Response(500, json={"error": "unexpected"})


@pytest.fixture
def owner(db: Session) -> User:
    user = User(
        email=f"pn-owner-{uuid4().hex[:8]}@picknext.local",
        display_name="PN Owner",
        password_hash="hash",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def category(db: Session, owner: User) -> Category:
    cat = Category(
        user_id=owner.id,
        name="영화",
        category_type=CategoryType.MEDIA,
        sort_order=1,
    )
    db.add(cat)
    db.flush()
    return cat


@pytest.fixture
def api_client(db: Session, owner: User):
    app = create_app()

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: owner
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def tmdb_client(db: Session, owner: User):
    router = _Router()
    transport = httpx.MockTransport(router)
    settings = Settings(
        _env_file=None,
        tmdb_api_read_access_token=SecretStr("test-token"),
        tmdb_api_key=None,
    )
    mock_http = httpx.AsyncClient(transport=transport)
    service = TmdbService(settings, TmdbClient(settings, mock_http))
    app = create_app()

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: owner
    app.dependency_overrides[get_tmdb_service] = lambda: service
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_progress_note_column_is_text(db: Session) -> None:
    row = db.execute(
        text(
            """
            SELECT data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'items' AND column_name = 'progress_note'
            """
        )
    ).one()
    assert row.data_type == "text"
    assert row.character_maximum_length is None


def test_create_progress_note_over_200(api_client: TestClient, category: Category) -> None:
    note = "N" * 250
    response = api_client.post(
        "/api/v1/items",
        json={
            "title": "긴노트",
            "category_id": str(category.id),
            "progress_note": note,
        },
    )
    assert response.status_code == 201
    assert response.json()["progress_note"] == note


def test_patch_progress_note_over_200(
    api_client: TestClient, db: Session, owner: User, category: Category
) -> None:
    item = Item(
        user_id=owner.id,
        category_id=category.id,
        title="패치대상",
        status=ItemStatus.PLANNED,
        rating=Decimal("0.0"),
        progress_note="짧음",
    )
    db.add(item)
    db.flush()
    note = "P" * 303
    response = api_client.patch(
        f"/api/v1/items/{item.id}",
        json={"progress_note": note},
    )
    assert response.status_code == 200
    assert response.json()["progress_note"] == note


def test_progress_note_whitespace_normalization(
    api_client: TestClient, category: Category
) -> None:
    created = api_client.post(
        "/api/v1/items",
        json={
            "title": "공백",
            "category_id": str(category.id),
            "progress_note": "  시즌 2  ",
        },
    )
    assert created.status_code == 201
    assert created.json()["progress_note"] == "시즌 2"

    blank = api_client.post(
        "/api/v1/items",
        json={
            "title": "공백2",
            "category_id": str(category.id),
            "progress_note": "   ",
        },
    )
    assert blank.status_code == 201
    assert blank.json()["progress_note"] is None


def test_tmdb_register_progress_note_over_200(
    tmdb_client: TestClient, category: Category
) -> None:
    note = "T" * 237
    response = tmdb_client.post(
        "/api/v1/items/from-tmdb",
        json={
            "media_type": "movie",
            "tmdb_id": 872585,
            "category_id": str(category.id),
            "progress_note": note,
        },
    )
    assert response.status_code == 201
    assert response.json()["progress_note"] == note
