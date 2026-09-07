"""ITEM-UX-2: TMDB search duplicate candidate detection."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.v1.tmdb import get_tmdb_service
from app.core.config import Settings
from app.db.session import get_db
from app.integrations.tmdb.client import TmdbClient
from app.main import create_app
from app.models import Category, CategoryType, Item, ItemStatus, User
from app.services.tmdb_service import (
    MAX_DUPLICATE_CANDIDATES,
    TmdbService,
    normalize_title_for_match,
)


CONFIGURATION = {
    "images": {
        "secure_base_url": "https://image.tmdb.org/t/p/",
        "poster_sizes": ["w92", "w500", "original"],
        "backdrop_sizes": ["w300", "w780", "original"],
        "profile_sizes": ["w45", "w185", "original"],
    }
}


def _parasite_search_payload() -> dict[str, Any]:
    return {
        "page": 1,
        "total_pages": 1,
        "total_results": 1,
        "results": [
            {
                "id": 496243,
                "title": "기생충",
                "original_title": "Parasite",
                "overview": "줄거리",
                "original_language": "ko",
                "release_date": "2019-05-30",
                "genre_ids": [18],
                "poster_path": "/p.jpg",
                "backdrop_path": "/b.jpg",
                "adult": False,
                "popularity": 10.0,
                "vote_average": 8.5,
                "vote_count": 100,
            }
        ],
    }


def _multi_title_payload() -> dict[str, Any]:
    return {
        "page": 1,
        "total_pages": 1,
        "total_results": 2,
        "results": [
            {
                "id": 496243,
                "title": "기생충",
                "original_title": "Parasite",
                "release_date": "2019-05-30",
                "poster_path": None,
            },
            {
                "id": 999001,
                "title": "다른작품",
                "original_title": "Other",
                "release_date": "2020-01-01",
                "poster_path": None,
            },
        ],
    }


class CandidateRouter:
    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        self.payload = payload or _parasite_search_payload()
        self.calls: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        path = request.url.path
        if path.endswith("/configuration"):
            return httpx.Response(200, json=CONFIGURATION)
        if path.endswith("/search/movie"):
            return httpx.Response(200, json=self.payload)
        return httpx.Response(500, json={"error": "unexpected"})


@pytest.fixture
def owner(db: Session) -> User:
    user = User(
        email=f"cand-owner-{uuid4().hex[:8]}@picknext.local",
        display_name="Candidate Owner",
        password_hash="hash",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def other_user(db: Session) -> User:
    user = User(
        email=f"cand-other-{uuid4().hex[:8]}@picknext.local",
        display_name="Other User",
        password_hash="hash",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _category_for(db: Session, user: User, name: str = "영화") -> Category:
    category = Category(
        user_id=user.id,
        name=name,
        category_type=CategoryType.MEDIA,
        sort_order=1,
    )
    db.add(category)
    db.flush()
    return category


def _manual_item(
    db: Session,
    *,
    user: User,
    category: Category,
    title: str,
    original_title: str | None = None,
    release_year: int | None = None,
    external_source: str | None = None,
    external_id: str | None = None,
    external_media_type: str | None = None,
) -> Item:
    item = Item(
        user_id=user.id,
        category_id=category.id,
        title=title,
        original_title=original_title,
        release_year=release_year,
        status=ItemStatus.PLANNED,
        rating=Decimal("0.0"),
        external_source=external_source,
        external_id=external_id,
        external_media_type=external_media_type,
    )
    db.add(item)
    db.flush()
    return item


@pytest.fixture
def candidate_api(db: Session, owner: User):
    router = CandidateRouter()
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
        yield client, router, owner, service

    app.dependency_overrides.clear()


def test_normalize_title_for_match() -> None:
    assert normalize_title_for_match("  기생충  ") == "기생충"
    assert normalize_title_for_match("Parasite") == "parasite"
    assert normalize_title_for_match("A\u00a0B") == "a b"
    assert normalize_title_for_match("Parasite  Movie") == "parasite movie"
    assert normalize_title_for_match("Ｐａｒａｓｉｔｅ") == "parasite"
    assert normalize_title_for_match("   ") is None
    assert normalize_title_for_match(None) is None


def test_exact_registered_excludes_same_item_from_candidates(
    candidate_api, db: Session
) -> None:
    client, _, owner, _ = candidate_api
    category = _category_for(db, owner)
    item = _manual_item(
        db,
        user=owner,
        category=category,
        title="기생충",
        release_year=2019,
        external_source="tmdb",
        external_id="496243",
        external_media_type="movie",
    )

    response = client.get(
        "/api/v1/tmdb/search",
        params={"query": "기생충", "media_type": "movie"},
    )
    assert response.status_code == 200
    row = response.json()["results"][0]
    assert row["registered"] is True
    assert row["registered_item_id"] == str(item.id)
    assert row["duplicate_candidates"] == []


def test_manual_title_year_candidate(candidate_api, db: Session) -> None:
    client, _, owner, _ = candidate_api
    category = _category_for(db, owner)
    item = _manual_item(
        db,
        user=owner,
        category=category,
        title="기생충",
        release_year=2019,
    )

    response = client.get(
        "/api/v1/tmdb/search",
        params={"query": "기생충", "media_type": "movie"},
    )
    assert response.status_code == 200
    row = response.json()["results"][0]
    assert row["registered"] is False
    assert row["registered_item_id"] is None
    candidates = row["duplicate_candidates"]
    assert len(candidates) == 1
    assert candidates[0]["item_id"] == str(item.id)
    assert candidates[0]["title"] == "기생충"
    assert candidates[0]["release_year"] == 2019
    assert candidates[0]["match_type"] == "TITLE_YEAR"


def test_trailing_whitespace_title_still_candidate(candidate_api, db: Session) -> None:
    """SQL prefilter must not drop Item titles with trailing spaces."""
    client, _, owner, _ = candidate_api
    category = _category_for(db, owner)
    item = _manual_item(
        db,
        user=owner,
        category=category,
        title="기생충   ",
        release_year=2019,
    )

    response = client.get(
        "/api/v1/tmdb/search",
        params={"query": "기생충", "media_type": "movie"},
    )
    assert response.status_code == 200
    candidates = response.json()["results"][0]["duplicate_candidates"]
    assert len(candidates) == 1
    assert candidates[0]["item_id"] == str(item.id)
    assert candidates[0]["match_type"] == "TITLE_YEAR"


def test_consecutive_whitespace_title_still_candidate(
    candidate_api, db: Session
) -> None:
    """Internal whitespace collapse must survive SQL prefilter."""
    client, router, owner, _ = candidate_api
    router.payload = {
        "page": 1,
        "total_pages": 1,
        "total_results": 1,
        "results": [
            {
                "id": 88001,
                "title": "Parasite Movie",
                "original_title": "Parasite Movie",
                "release_date": "2019-05-30",
                "poster_path": None,
            }
        ],
    }
    category = _category_for(db, owner)
    item = _manual_item(
        db,
        user=owner,
        category=category,
        title="Parasite  Movie",
        release_year=2019,
    )

    response = client.get(
        "/api/v1/tmdb/search",
        params={"query": "Parasite Movie", "media_type": "movie"},
    )
    assert response.status_code == 200
    candidates = response.json()["results"][0]["duplicate_candidates"]
    assert len(candidates) == 1
    assert candidates[0]["item_id"] == str(item.id)
    assert candidates[0]["match_type"] == "TITLE_YEAR"


def test_case_difference_english_title_still_candidate(
    candidate_api, db: Session
) -> None:
    client, _, owner, _ = candidate_api
    category = _category_for(db, owner)
    item = _manual_item(
        db,
        user=owner,
        category=category,
        title="PARASITE",
        release_year=2019,
    )

    response = client.get(
        "/api/v1/tmdb/search",
        params={"query": "기생충", "media_type": "movie"},
    )
    assert response.status_code == 200
    candidates = response.json()["results"][0]["duplicate_candidates"]
    assert len(candidates) == 1
    assert candidates[0]["item_id"] == str(item.id)
    # TMDB original_title "Parasite" matches Item.title after casefold.
    assert candidates[0]["match_type"] == "ORIGINAL_TITLE_YEAR"


def test_nfkc_fullwidth_title_still_candidate(candidate_api, db: Session) -> None:
    client, _, owner, _ = candidate_api
    category = _category_for(db, owner)
    item = _manual_item(
        db,
        user=owner,
        category=category,
        title="Ｐａｒａｓｉｔｅ",
        release_year=2019,
    )

    response = client.get(
        "/api/v1/tmdb/search",
        params={"query": "기생충", "media_type": "movie"},
    )
    assert response.status_code == 200
    candidates = response.json()["results"][0]["duplicate_candidates"]
    assert len(candidates) == 1
    assert candidates[0]["item_id"] == str(item.id)
    assert candidates[0]["match_type"] == "ORIGINAL_TITLE_YEAR"


def test_original_title_year_candidate(candidate_api, db: Session) -> None:
    client, _, owner, _ = candidate_api
    category = _category_for(db, owner)
    item = _manual_item(
        db,
        user=owner,
        category=category,
        title="파라사이트",
        original_title="Parasite",
        release_year=2019,
    )

    response = client.get(
        "/api/v1/tmdb/search",
        params={"query": "기생충", "media_type": "movie"},
    )
    assert response.status_code == 200
    row = response.json()["results"][0]
    assert row["registered"] is False
    candidates = row["duplicate_candidates"]
    assert len(candidates) == 1
    assert candidates[0]["item_id"] == str(item.id)
    assert candidates[0]["match_type"] == "ORIGINAL_TITLE_YEAR"


def test_different_year_not_candidate(candidate_api, db: Session) -> None:
    client, _, owner, _ = candidate_api
    category = _category_for(db, owner)
    _manual_item(
        db,
        user=owner,
        category=category,
        title="기생충",
        release_year=2005,
    )

    response = client.get(
        "/api/v1/tmdb/search",
        params={"query": "기생충", "media_type": "movie"},
    )
    assert response.status_code == 200
    row = response.json()["results"][0]
    assert row["registered"] is False
    assert row["duplicate_candidates"] == []


def test_null_year_weak_candidate(candidate_api, db: Session) -> None:
    client, _, owner, _ = candidate_api
    category = _category_for(db, owner)
    item = _manual_item(
        db,
        user=owner,
        category=category,
        title="기생충",
        release_year=None,
    )

    response = client.get(
        "/api/v1/tmdb/search",
        params={"query": "기생충", "media_type": "movie"},
    )
    assert response.status_code == 200
    row = response.json()["results"][0]
    candidates = row["duplicate_candidates"]
    assert len(candidates) == 1
    assert candidates[0]["item_id"] == str(item.id)
    assert candidates[0]["match_type"] == "TITLE_NULL_YEAR"
    assert candidates[0]["release_year"] is None


def test_other_user_items_excluded(
    candidate_api, db: Session, other_user: User
) -> None:
    client, _, owner, _ = candidate_api
    owner_category = _category_for(db, owner, name="영화-owner")
    other_category = _category_for(db, other_user, name="영화-other")
    _manual_item(
        db,
        user=other_user,
        category=other_category,
        title="기생충",
        release_year=2019,
    )
    own = _manual_item(
        db,
        user=owner,
        category=owner_category,
        title="기생충",
        release_year=2019,
    )

    response = client.get(
        "/api/v1/tmdb/search",
        params={"query": "기생충", "media_type": "movie"},
    )
    assert response.status_code == 200
    candidates = response.json()["results"][0]["duplicate_candidates"]
    assert [c["item_id"] for c in candidates] == [str(own.id)]


def test_candidate_limit(candidate_api, db: Session) -> None:
    client, _, owner, _ = candidate_api
    category = _category_for(db, owner)
    created_ids: list[str] = []
    for index in range(MAX_DUPLICATE_CANDIDATES + 3):
        item = _manual_item(
            db,
            user=owner,
            category=category,
            title="기생충",
            release_year=2019 if index % 2 == 0 else None,
        )
        created_ids.append(str(item.id))

    response = client.get(
        "/api/v1/tmdb/search",
        params={"query": "기생충", "media_type": "movie"},
    )
    assert response.status_code == 200
    candidates = response.json()["results"][0]["duplicate_candidates"]
    assert len(candidates) == MAX_DUPLICATE_CANDIDATES
    # Strong TITLE_YEAR matches should come before NULL year matches.
    assert candidates[0]["match_type"] == "TITLE_YEAR"
    assert all(c["item_id"] in created_ids for c in candidates)


def test_candidate_lookup_not_n_plus_one(db: Session, owner: User) -> None:
    """Batch candidate lookup issues a constant number of SELECTs (not per result)."""
    category = _category_for(db, owner)
    for index in range(8):
        _manual_item(
            db,
            user=owner,
            category=category,
            title="기생충",
            release_year=2019 if index < 4 else None,
        )

    settings = Settings(
        _env_file=None,
        tmdb_api_read_access_token=SecretStr("test-token"),
        tmdb_api_key=None,
    )
    service = TmdbService(
        settings,
        TmdbClient(settings, httpx.AsyncClient()),
    )

    from app.schemas.tmdb import TmdbSearchResultItem

    results = [
        TmdbSearchResultItem(
            tmdb_id=496243 + i,
            media_type="movie",
            title="기생충",
            original_title="Parasite",
            release_year=2019,
            registered=False,
            registered_item_id=None,
        )
        for i in range(12)
    ]

    statements: list[str] = []

    def before_cursor(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        statements.append(str(statement))

    event.listen(db.bind, "before_cursor_execute", before_cursor)
    try:
        mapping = service._duplicate_candidates_by_result(db, owner, results)
    finally:
        event.remove(db.bind, "before_cursor_execute", before_cursor)

    assert len(mapping) == 12
    select_count = sum(1 for sql in statements if sql.lstrip().upper().startswith("SELECT"))
    # One batch SELECT for all results — not one per TMDB row.
    assert select_count == 1


def test_search_response_includes_empty_candidates_by_default(
    candidate_api, db: Session
) -> None:
    client, _, owner, _ = candidate_api
    _category_for(db, owner)
    response = client.get(
        "/api/v1/tmdb/search",
        params={"query": "기생충", "media_type": "movie"},
    )
    assert response.status_code == 200
    row = response.json()["results"][0]
    assert "duplicate_candidates" in row
    assert row["duplicate_candidates"] == []
    assert row["registered"] is False
