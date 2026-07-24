"""TMDB search/details API integration tests with MockTransport."""

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
from app.core.config import Settings, get_settings
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


def _movie_search_payload() -> dict[str, Any]:
    return {
        "page": 1,
        "total_pages": 1,
        "total_results": 1,
        "results": [
            {
                "id": 872585,
                "title": "오펜하이머",
                "original_title": "Oppenheimer",
                "overview": "줄거리",
                "original_language": "en",
                "release_date": "2023-07-19",
                "genre_ids": [18],
                "poster_path": "/poster.jpg",
                "backdrop_path": "/back.jpg",
                "adult": False,
                "popularity": 10.5,
                "vote_average": 8.1,
                "vote_count": 100,
            },
            {
                "id": 2,
                "title": "깨진날짜",
                "original_title": "Broken",
                "release_date": "",
                "poster_path": None,
                "backdrop_path": None,
            },
        ],
    }


def _multi_search_payload() -> dict[str, Any]:
    return {
        "page": 1,
        "total_pages": 5,
        "total_results": 91,
        "results": [
            {
                "id": 93405,
                "media_type": "tv",
                "name": "오징어 게임",
                "original_name": "Squid Game",
                "first_air_date": "2021-09-17",
                "poster_path": "/sg.jpg",
            },
            {
                "id": 100,
                "media_type": "person",
                "name": "Actor",
            },
            {
                "id": 872585,
                "media_type": "movie",
                "title": "오펜하이머",
                "original_title": "Oppenheimer",
                "release_date": "2023-07-19",
            },
        ],
    }


def _movie_details_payload() -> dict[str, Any]:
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
        "credits": {
            "cast": [
                {
                    "id": i,
                    "name": f"Actor{i}",
                    "character": f"C{i}",
                    "order": i,
                    "profile_path": None,
                }
                for i in range(15)
            ],
            "crew": [
                {"id": 9, "name": "Nolan", "job": "Director", "profile_path": "/n.jpg"},
                {"id": 8, "name": "Other", "job": "Writer", "profile_path": None},
            ],
        },
        "external_ids": {
            "imdb_id": "tt15398776",
            "wikidata_id": None,
            "facebook_id": None,
            "instagram_id": None,
            "twitter_id": None,
        },
    }


def _tv_details_payload() -> dict[str, Any]:
    return {
        "id": 93405,
        "name": "오징어 게임",
        "original_name": "Squid Game",
        "overview": "tv",
        "first_air_date": "2021-09-17",
        "last_air_date": "2025-01-01",
        "episode_run_time": [54],
        "number_of_seasons": 2,
        "number_of_episodes": 16,
        "genres": [{"id": 18, "name": "드라마"}],
        "created_by": [{"id": 1, "name": "황동혁", "profile_path": None}],
        "credits": {"cast": [], "crew": []},
        "external_ids": {"imdb_id": "tt10919420"},
        "poster_path": None,
        "backdrop_path": None,
    }


class FakeTmdbRouter:
    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        path = request.url.path
        if path.endswith("/configuration"):
            return httpx.Response(200, json=CONFIGURATION)
        if path.endswith("/search/movie"):
            return httpx.Response(200, json=_movie_search_payload())
        if path.endswith("/search/tv"):
            return httpx.Response(
                200,
                json={
                    "page": 1,
                    "total_pages": 1,
                    "total_results": 1,
                    "results": [
                        {
                            "id": 93405,
                            "name": "오징어 게임",
                            "original_name": "Squid Game",
                            "first_air_date": "2021-09-17",
                        }
                    ],
                },
            )
        if path.endswith("/search/multi"):
            return httpx.Response(200, json=_multi_search_payload())
        if "/movie/" in path:
            if path.endswith("/999999"):
                return httpx.Response(404, json={"status_code": 34})
            return httpx.Response(200, json=_movie_details_payload())
        if "/tv/" in path:
            return httpx.Response(200, json=_tv_details_payload())
        return httpx.Response(500, json={"error": "unexpected"})


@pytest.fixture
def owner(db: Session) -> User:
    user = User(
        email=f"tmdb-owner-{uuid4().hex[:8]}@picknext.local",
        display_name="TMDB Owner",
        password_hash="hash",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def tmdb_api(db: Session, owner: User):
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


def test_status_available(tmdb_api) -> None:
    client, _, _ = tmdb_api
    response = client.get("/api/v1/tmdb/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "AVAILABLE"
    assert body["auth_mode"] == "bearer"
    assert "test-token" not in str(body)


def test_search_movie_normalized(tmdb_api) -> None:
    client, router, _ = tmdb_api
    response = client.get(
        "/api/v1/tmdb/search",
        params={"query": " 오펜하이머 ", "media_type": "movie", "page": 1},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "오펜하이머"
    assert body["media_type"] == "movie"
    assert body["returned_count"] == 2
    first = body["results"][0]
    assert first["tmdb_id"] == 872585
    assert first["media_type"] == "movie"
    assert first["title"] == "오펜하이머"
    assert first["release_year"] == 2023
    assert first["poster_url"] == "https://image.tmdb.org/t/p/w500/poster.jpg"
    assert body["results"][1]["release_date"] is None
    assert body["results"][1]["poster_url"] is None
    assert any(c.url.path.endswith("/search/movie") for c in router.calls)


def test_search_tv(tmdb_api) -> None:
    client, router, _ = tmdb_api
    response = client.get(
        "/api/v1/tmdb/search",
        params={"query": "오징어 게임", "media_type": "tv"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["media_type"] == "tv"
    assert body["results"][0]["title"] == "오징어 게임"
    assert any(c.url.path.endswith("/search/tv") for c in router.calls)


def test_search_multi_excludes_person(tmdb_api) -> None:
    client, _, _ = tmdb_api
    response = client.get(
        "/api/v1/tmdb/search",
        params={"query": "배트맨", "media_type": "all"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["upstream_total_results"] == 91
    assert body["upstream_total_pages"] == 5
    assert body["returned_count"] == 2
    assert all(r["media_type"] in ("movie", "tv") for r in body["results"])


def test_search_blank_query_rejected(tmdb_api) -> None:
    client, _, _ = tmdb_api
    response = client.get("/api/v1/tmdb/search", params={"query": "   "})
    assert response.status_code == 422


def test_search_invalid_media_type(tmdb_api) -> None:
    client, _, _ = tmdb_api
    response = client.get(
        "/api/v1/tmdb/search",
        params={"query": "x", "media_type": "person"},
    )
    assert response.status_code == 422


def test_search_registered_flag(tmdb_api, db: Session) -> None:
    client, _, owner = tmdb_api
    category = Category(
        user_id=owner.id,
        name="영화",
        category_type=CategoryType.MEDIA,
        sort_order=1,
    )
    db.add(category)
    db.flush()
    item = Item(
        user_id=owner.id,
        category_id=category.id,
        title="오펜하이머",
        status=ItemStatus.PLANNED,
        rating=Decimal("0.0"),
        external_source="tmdb",
        external_id="872585",
        external_media_type="movie",
    )
    db.add(item)
    db.flush()

    response = client.get(
        "/api/v1/tmdb/search",
        params={"query": "오펜하이머", "media_type": "movie"},
    )
    assert response.status_code == 200
    by_id = {r["tmdb_id"]: r for r in response.json()["results"]}
    assert by_id[872585]["registered"] is True
    assert by_id[872585]["registered_item_id"] == str(item.id)
    assert by_id[2]["registered"] is False


def test_movie_details(tmdb_api) -> None:
    client, _, _ = tmdb_api
    response = client.get("/api/v1/tmdb/details/movie/872585")
    assert response.status_code == 200
    body = response.json()
    assert body["runtime_minutes"] == 181
    assert body["genres"][0]["name"] == "드라마"
    assert len(body["cast"]) == 10
    assert body["directors"][0]["name"] == "Nolan"
    assert body["external_ids"]["imdb_id"] == "tt15398776"
    assert body["poster_url"].endswith("/w500/p.jpg")


def test_tv_details(tmdb_api) -> None:
    client, _, _ = tmdb_api
    response = client.get("/api/v1/tmdb/details/tv/93405")
    assert response.status_code == 200
    body = response.json()
    assert body["number_of_seasons"] == 2
    assert body["number_of_episodes"] == 16
    assert body["creators"][0]["name"] == "황동혁"
    assert body["directors"] == []


def test_details_not_found(tmdb_api) -> None:
    client, _, _ = tmdb_api
    response = client.get("/api/v1/tmdb/details/movie/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "TMDB_NOT_FOUND"


def test_details_invalid_media_type(tmdb_api) -> None:
    client, _, _ = tmdb_api
    response = client.get("/api/v1/tmdb/details/person/1")
    assert response.status_code == 422


def test_not_configured_search(db: Session, owner: User) -> None:
    settings = Settings(
        _env_file=None,
        tmdb_api_read_access_token=None,
        tmdb_api_key=None,
    )
    mock_http = httpx.AsyncClient()
    service = TmdbService(settings, TmdbClient(settings, mock_http))
    app = create_app()

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: owner
    app.dependency_overrides[get_tmdb_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/api/v1/tmdb/search", params={"query": "x"})
        assert response.status_code == 503
        assert response.json()["detail"] == "TMDB_NOT_CONFIGURED"
        status = client.get("/api/v1/tmdb/status")
        assert status.status_code == 200
        assert status.json()["status"] == "NOT_CONFIGURED"
        health = client.get("/api/v1/health")
        assert health.status_code == 200

    app.dependency_overrides.clear()
