"""Login, session cookie, and logout tests (AUTH-1)."""

from __future__ import annotations

import hashlib
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, hash_session_token, verify_password
from app.models import User, UserSession

TEST_PASSWORD = "test-password-ok"


def _auth_detail(resp) -> dict:
    detail = resp.json()["detail"]
    return detail if isinstance(detail, dict) else {"code": detail}


def _unique_login_id() -> str:
    return f"user{uuid4().hex[:8]}"


@pytest.fixture
def login_user(db: Session) -> tuple[str, str, User]:
    login_id = _unique_login_id()
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
    return login_id, TEST_PASSWORD, user


def test_login_sets_session_cookie_and_me_works(
    client: TestClient,
    login_user: tuple[str, str, User],
) -> None:
    login_id, password, user = login_user
    settings = get_settings()

    response = client.post(
        "/api/v1/auth/login",
        json={"login_id": login_id, "password": password, "remember_me": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["login_id"] == login_id
    assert body["email"] == user.email
    assert settings.auth_cookie_name in response.cookies

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == str(user.id)


def test_logout_revokes_session(
    client: TestClient,
    db: Session,
    login_user: tuple[str, str, User],
) -> None:
    login_id, password, _user = login_user

    login = client.post(
        "/api/v1/auth/login",
        json={"login_id": login_id, "password": password, "remember_me": False},
    )
    assert login.status_code == 200
    cookie_value = login.cookies[get_settings().auth_cookie_name]

    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 200

    token_hash = hash_session_token(cookie_value)
    row = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash))
    assert row is not None
    assert row.revoked_at is not None

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 401
    assert _auth_detail(me)["code"] in {"AUTH_REQUIRED", "AUTH_SESSION_EXPIRED"}


def test_login_wrong_credentials(
    client: TestClient,
    login_user: tuple[str, str, User],
) -> None:
    login_id, _password, _user = login_user

    response = client.post(
        "/api/v1/auth/login",
        json={"login_id": login_id, "password": "wrong-password-value", "remember_me": False},
    )
    assert response.status_code == 401
    assert _auth_detail(response)["code"] == "AUTH_INVALID_CREDENTIALS"


def test_login_inactive_user_same_error(
    client: TestClient,
    db: Session,
    login_user: tuple[str, str, User],
) -> None:
    login_id, password, user = login_user
    user.is_active = False
    db.flush()

    response = client.post(
        "/api/v1/auth/login",
        json={"login_id": login_id, "password": password, "remember_me": False},
    )
    assert response.status_code == 401
    assert _auth_detail(response)["code"] == "AUTH_INVALID_CREDENTIALS"


def test_remember_me_cookie_has_max_age(
    client: TestClient,
    login_user: tuple[str, str, User],
) -> None:
    login_id, password, _user = login_user
    settings = get_settings()

    response = client.post(
        "/api/v1/auth/login",
        json={"login_id": login_id, "password": password, "remember_me": True},
    )
    assert response.status_code == 200

    set_cookie = response.headers.get("set-cookie", "")
    assert settings.auth_cookie_name in set_cookie
    assert "max-age=" in set_cookie.lower()


def test_login_without_remember_me_omits_max_age(
    client: TestClient,
    login_user: tuple[str, str, User],
) -> None:
    login_id, password, _user = login_user

    response = client.post(
        "/api/v1/auth/login",
        json={"login_id": login_id, "password": password, "remember_me": False},
    )
    assert response.status_code == 200

    set_cookie = response.headers.get("set-cookie", "")
    assert "max-age=" not in set_cookie.lower()


def test_legacy_sha256_hash_cannot_login(
    client: TestClient,
    db: Session,
) -> None:
    login_id = _unique_login_id()
    email = f"{login_id}@example.com"
    user = User(
        email=email,
        display_name=login_id,
        login_id=login_id,
        password_hash=hashlib.sha256(TEST_PASSWORD.encode("utf-8")).hexdigest(),
        is_active=True,
    )
    db.add(user)
    db.flush()

    response = client.post(
        "/api/v1/auth/login",
        json={"login_id": login_id, "password": TEST_PASSWORD, "remember_me": False},
    )
    assert response.status_code == 401
    assert _auth_detail(response)["code"] == "AUTH_INVALID_CREDENTIALS"
    assert verify_password(TEST_PASSWORD, user.password_hash) is False
