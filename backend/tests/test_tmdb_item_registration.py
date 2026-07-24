"""TMDB item registration API tests (POST /items/from-tmdb)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.v1.tmdb import get_tmdb_service
from app.core.config import Settings
from app.db.session import get_db
from app.integrations.tmdb.client import TmdbClient
from app.main import create_app
from app.models import Category, CategoryType, Collection, Item, ItemStatus, User
from app.services.tmdb_service import TmdbService

CONFIGURATION = {
    "images": {
        "secure_base_url": "https://image.tmdb.org/t/p/",
        "poster_sizes": ["w92", "w500", "original"],
        "backdrop_sizes": ["w300", "w780", "original"],
        "profile_sizes": ["w45", "w185", "original"],
    }
}


def _movie_details_payload() -> dict[str, Any]:
    return {
        "id": 872585,
        "title": "오펜하이머",
        "original_title": "Oppenheimer",
        "overview": "줄거리",
        "original_language": "en",
        "release_date": "2023-07-19",
        "runtime": 181,
        "genres": [{"id": 18, "name": "드라마"}],
        "poster_path": "/p.jpg",
        "backdrop_path": "/b.jpg",
        "credits": {"cast": [], "crew": []},
        "external_ids": {"imdb_id": "tt15398776"},
    }


def _tv_details_payload() -> dict[str, Any]:
    return {
        "id": 93405,
        "name": "오징어 게임",
        "original_name": "Squid Game",
        "overview": "tv",
        "original_language": "ko",
        "first_air_date": "2021-09-17",
        "genres": [{"id": 18, "name": "드라마"}],
        "created_by": [],
        "credits": {"cast": [], "crew": []},
        "external_ids": {"imdb_id": "tt10919420"},
        "poster_path": "/tv.jpg",
        "backdrop_path": "/tvb.jpg",
    }


class FakeTmdbRouter:
    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []
        self.include_search: bool = False
        self.movie_details_override: dict[str, Any] | None = None
        self.tv_details_override: dict[str, Any] | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        path = request.url.path
        if path.endswith("/configuration"):
            return httpx.Response(200, json=CONFIGURATION)
        if self.include_search and path.endswith("/search/movie"):
            return httpx.Response(
                200,
                json={
                    "page": 1,
                    "total_pages": 1,
                    "total_results": 1,
                    "results": [
                        {
                            "id": 872585,
                            "title": "오펜하이머",
                            "original_title": "Oppenheimer",
                            "release_date": "2023-07-19",
                            "poster_path": "/p.jpg",
                        }
                    ],
                },
            )
        if "/movie/" in path:
            if path.endswith("/999999"):
                return httpx.Response(404, json={"status_code": 34})
            payload = (
                self.movie_details_override
                if self.movie_details_override is not None
                else _movie_details_payload()
            )
            return httpx.Response(200, json=payload)
        if "/tv/" in path:
            payload = (
                self.tv_details_override
                if self.tv_details_override is not None
                else _tv_details_payload()
            )
            return httpx.Response(200, json=payload)
        return httpx.Response(500, json={"error": "unexpected"})


@pytest.fixture
def owner(db: Session) -> User:
    user = User(
        email=f"tmdb-reg-{uuid4().hex[:8]}@picknext.local",
        display_name="TMDB Reg Owner",
        password_hash="hash",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def other_user(db: Session) -> User:
    user = User(
        email=f"tmdb-other-{uuid4().hex[:8]}@picknext.local",
        display_name="Other",
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
def tmdb_reg_api(db: Session, owner: User):
    router = FakeTmdbRouter()
    transport = httpx.MockTransport(router)
    settings = Settings(
        _env_file=None,
        tmdb_api_read_access_token=SecretStr("test-token"),
        tmdb_api_key=None,
        tmdb_language="ko-KR",
        tmdb_region="KR",
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
        yield client, router, owner

    app.dependency_overrides.clear()


def test_register_movie_from_tmdb(
    tmdb_reg_api, db: Session, category: Category
) -> None:
    client, router, owner = tmdb_reg_api
    response = client.post(
        "/api/v1/items/from-tmdb",
        json={
            "media_type": "movie",
            "tmdb_id": 872585,
            "category_id": str(category.id),
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "오펜하이머"
    assert body["external_source"] == "tmdb"
    assert body["external_id"] == "872585"
    assert body["external_media_type"] == "movie"
    assert body["original_title"] == "Oppenheimer"
    assert body["original_language"] == "en"
    assert body["poster_path"] == "/p.jpg"
    assert body["backdrop_path"] == "/b.jpg"
    assert body["release_year"] == 2023
    assert body["poster_url"] == "https://image.tmdb.org/t/p/w500/p.jpg"
    assert body["backdrop_url"] == "https://image.tmdb.org/t/p/w780/b.jpg"
    assert body["synopsis"] == "줄거리"
    assert body["status"] == "PLANNED"
    assert body["rating"] == 0.0
    assert body["category"]["id"] == str(category.id)
    assert any("/movie/872585" in c.url.path for c in router.calls)

    stored = db.get(Item, body["id"])
    assert stored is not None
    assert stored.user_id == owner.id
    assert stored.external_metadata_updated_at is not None


def test_register_tv_from_tmdb(tmdb_reg_api, category: Category) -> None:
    client, _, _ = tmdb_reg_api
    response = client.post(
        "/api/v1/items/from-tmdb",
        json={
            "media_type": "tv",
            "tmdb_id": 93405,
            "category_id": str(category.id),
            "title": "오징어게임 커스텀",
            "memo": "볼 예정",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "오징어게임 커스텀"
    assert body["external_media_type"] == "tv"
    assert body["external_id"] == "93405"
    assert body["original_title"] == "Squid Game"
    assert body["release_year"] == 2021
    assert body["poster_url"] == "https://image.tmdb.org/t/p/w500/tv.jpg"
    assert body["synopsis"] == "tv"
    assert body["memo"] == "볼 예정"


def test_register_movie_blank_overview_sets_null_synopsis(
    tmdb_reg_api, category: Category
) -> None:
    client, router, _ = tmdb_reg_api
    payload = _movie_details_payload()
    payload["overview"] = "   "
    router.movie_details_override = payload
    response = client.post(
        "/api/v1/items/from-tmdb",
        json={
            "media_type": "movie",
            "tmdb_id": 872585,
            "category_id": str(category.id),
        },
    )
    assert response.status_code == 201
    assert response.json()["synopsis"] is None


def test_forged_synopsis_not_accepted_on_from_tmdb(
    tmdb_reg_api, category: Category
) -> None:
    client, _, _ = tmdb_reg_api
    response = client.post(
        "/api/v1/items/from-tmdb",
        json={
            "media_type": "movie",
            "tmdb_id": 872585,
            "category_id": str(category.id),
            "synopsis": "위조 줄거리",
        },
    )
    assert response.status_code == 422


def test_register_movie_missing_date_sets_null_year(
    tmdb_reg_api, category: Category
) -> None:
    client, router, _ = tmdb_reg_api
    payload = _movie_details_payload()
    payload["release_date"] = ""
    router.movie_details_override = payload
    response = client.post(
        "/api/v1/items/from-tmdb",
        json={
            "media_type": "movie",
            "tmdb_id": 872585,
            "category_id": str(category.id),
        },
    )
    assert response.status_code == 201
    assert response.json()["release_year"] is None


def test_forged_release_year_not_accepted_on_from_tmdb(
    tmdb_reg_api, category: Category
) -> None:
    client, _, _ = tmdb_reg_api
    response = client.post(
        "/api/v1/items/from-tmdb",
        json={
            "media_type": "movie",
            "tmdb_id": 872585,
            "category_id": str(category.id),
            "release_year": 1999,
        },
    )
    assert response.status_code == 422


def test_register_duplicate_returns_409(
    tmdb_reg_api, db: Session, category: Category
) -> None:
    client, _, owner = tmdb_reg_api
    existing = Item(
        user_id=owner.id,
        category_id=category.id,
        title="기존",
        status=ItemStatus.PLANNED,
        rating=Decimal("0.0"),
        external_source="tmdb",
        external_id="872585",
        external_media_type="movie",
    )
    db.add(existing)
    db.flush()

    response = client.post(
        "/api/v1/items/from-tmdb",
        json={
            "media_type": "movie",
            "tmdb_id": 872585,
            "category_id": str(category.id),
        },
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "TMDB_ITEM_ALREADY_EXISTS"
    assert detail["existing_item_id"] == str(existing.id)


def test_same_numeric_id_movie_and_tv_allowed(
    db: Session, owner: User, category: Category
) -> None:
    """movie/tv may share the same numeric TMDB id space."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/configuration"):
            return httpx.Response(200, json=CONFIGURATION)
        if "/movie/100" in path:
            payload = _movie_details_payload()
            payload["id"] = 100
            payload["title"] = "Movie100"
            return httpx.Response(200, json=payload)
        if "/tv/100" in path:
            payload = _tv_details_payload()
            payload["id"] = 100
            payload["name"] = "TV100"
            return httpx.Response(200, json=payload)
        return httpx.Response(500, json={"error": "unexpected"})

    settings = Settings(
        _env_file=None,
        tmdb_api_read_access_token=SecretStr("test-token"),
        tmdb_api_key=None,
    )
    mock_http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = TmdbService(settings, TmdbClient(settings, mock_http))
    app = create_app()

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: owner
    app.dependency_overrides[get_tmdb_service] = lambda: service

    with TestClient(app) as client:
        movie = client.post(
            "/api/v1/items/from-tmdb",
            json={
                "media_type": "movie",
                "tmdb_id": 100,
                "category_id": str(category.id),
            },
        )
        tv = client.post(
            "/api/v1/items/from-tmdb",
            json={
                "media_type": "tv",
                "tmdb_id": 100,
                "category_id": str(category.id),
            },
        )

    app.dependency_overrides.clear()
    assert movie.status_code == 201
    assert tv.status_code == 201
    assert movie.json()["external_id"] == "100"
    assert tv.json()["external_id"] == "100"
    assert movie.json()["external_media_type"] == "movie"
    assert tv.json()["external_media_type"] == "tv"
    assert movie.json()["id"] != tv.json()["id"]


def test_other_user_collection_404(
    tmdb_reg_api, db: Session, category: Category, other_user: User
) -> None:
    client, _, _ = tmdb_reg_api
    foreign = Collection(user_id=other_user.id, name="타컬렉션")
    db.add(foreign)
    db.flush()

    response = client.post(
        "/api/v1/items/from-tmdb",
        json={
            "media_type": "movie",
            "tmdb_id": 872585,
            "category_id": str(category.id),
            "collection_id": str(foreign.id),
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Collection not found"


def test_missing_category_404(tmdb_reg_api) -> None:
    client, _, _ = tmdb_reg_api
    response = client.post(
        "/api/v1/items/from-tmdb",
        json={
            "media_type": "movie",
            "tmdb_id": 872585,
            "category_id": str(uuid4()),
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Category not found"


def test_forged_external_fields_rejected(tmdb_reg_api, category: Category) -> None:
    client, _, _ = tmdb_reg_api
    response = client.post(
        "/api/v1/items/from-tmdb",
        json={
            "media_type": "movie",
            "tmdb_id": 872585,
            "category_id": str(category.id),
            "external_source": "forged",
            "poster_path": "/hack.jpg",
            "original_title": "Hacked",
        },
    )
    assert response.status_code == 422


def test_tmdb_not_found_mapped(tmdb_reg_api, category: Category) -> None:
    client, _, _ = tmdb_reg_api
    response = client.post(
        "/api/v1/items/from-tmdb",
        json={
            "media_type": "movie",
            "tmdb_id": 999999,
            "category_id": str(category.id),
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "TMDB_NOT_FOUND"


def test_register_then_search_shows_registered(
    tmdb_reg_api, category: Category
) -> None:
    client, router, _ = tmdb_reg_api
    created = client.post(
        "/api/v1/items/from-tmdb",
        json={
            "media_type": "movie",
            "tmdb_id": 872585,
            "category_id": str(category.id),
        },
    )
    assert created.status_code == 201
    item_id = created.json()["id"]

    router.include_search = True
    search = client.get(
        "/api/v1/tmdb/search",
        params={"query": "오펜하이머", "media_type": "movie"},
    )
    assert search.status_code == 200
    by_id = {r["tmdb_id"]: r for r in search.json()["results"]}
    assert by_id[872585]["registered"] is True
    assert by_id[872585]["registered_item_id"] == item_id
