"""Find-id and password reset recovery tests (AUTH-1)."""

from __future__ import annotations

import re
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, hash_session_token, verify_password
from app.models import AuthVerificationCode, User, UserSession

TEST_PASSWORD = "test-password-ok"
NEW_PASSWORD = "new-password-ok"


def _auth_detail(resp) -> dict:
    detail = resp.json()["detail"]
    return detail if isinstance(detail, dict) else {"code": detail}


def _unique_login_id() -> str:
    return f"user{uuid4().hex[:8]}"


def _extract_verification_code(body_text: str) -> str:
    match = re.search(r"\b(\d{6})\b", body_text)
    assert match is not None, f"6-digit code not found in email body: {body_text!r}"
    return match.group(1)


@pytest.fixture
def recovery_user(db: Session) -> tuple[str, str, User]:
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
    return login_id, email, user


def test_find_id_generic_response_for_missing_email(
    client: TestClient,
    fake_email_sender,
) -> None:
    response = client.post(
        "/api/v1/auth/find-id/request-code",
        json={"email": f"missing-{uuid4().hex[:8]}@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["message"]
    assert fake_email_sender.messages == []


def test_find_id_generic_response_for_existing_email(
    client: TestClient,
    recovery_user: tuple[str, str, User],
    fake_email_sender,
) -> None:
    _login_id, email, _user = recovery_user

    response = client.post(
        "/api/v1/auth/find-id/request-code",
        json={"email": email},
    )
    assert response.status_code == 200
    missing = client.post(
        "/api/v1/auth/find-id/request-code",
        json={"email": f"missing-{uuid4().hex[:8]}@example.com"},
    )
    assert response.json()["message"] == missing.json()["message"]
    assert len(fake_email_sender.messages) == 1


def test_find_id_verify_returns_login_id(
    client: TestClient,
    recovery_user: tuple[str, str, User],
    fake_email_sender,
) -> None:
    login_id, email, _user = recovery_user

    request = client.post(
        "/api/v1/auth/find-id/request-code",
        json={"email": email},
    )
    assert request.status_code == 200
    code = _extract_verification_code(fake_email_sender.messages[-1].body_text)

    verify = client.post(
        "/api/v1/auth/find-id/verify",
        json={"email": email, "verification_code": code},
    )
    assert verify.status_code == 200
    assert verify.json()["login_id"] == login_id


def test_password_reset_changes_hash_and_revokes_sessions(
    client: TestClient,
    db: Session,
    recovery_user: tuple[str, str, User],
    fake_email_sender,
) -> None:
    login_id, email, user = recovery_user
    old_hash = user.password_hash

    login = client.post(
        "/api/v1/auth/login",
        json={"login_id": login_id, "password": TEST_PASSWORD, "remember_me": False},
    )
    assert login.status_code == 200
    cookie_name = get_settings().auth_cookie_name
    old_cookie = login.cookies[cookie_name]

    request = client.post(
        "/api/v1/auth/password-reset/request-code",
        json={"login_id": login_id, "email": email},
    )
    assert request.status_code == 200
    code = _extract_verification_code(fake_email_sender.messages[-1].body_text)

    confirm = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "login_id": login_id,
            "email": email,
            "verification_code": code,
            "new_password": NEW_PASSWORD,
            "new_password_confirm": NEW_PASSWORD,
        },
    )
    assert confirm.status_code == 200

    db.refresh(user)
    assert user.password_hash != old_hash
    assert user.password_hash.startswith("$argon2")
    assert verify_password(NEW_PASSWORD, user.password_hash) is True
    assert verify_password(TEST_PASSWORD, user.password_hash) is False

    old_token_hash = hash_session_token(old_cookie)
    session = db.scalar(select(UserSession).where(UserSession.token_hash == old_token_hash))
    assert session is not None
    assert session.revoked_at is not None

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 401

    new_login = client.post(
        "/api/v1/auth/login",
        json={"login_id": login_id, "password": NEW_PASSWORD, "remember_me": False},
    )
    assert new_login.status_code == 200


def test_password_reset_request_code_email_unavailable(
    client: TestClient,
    db: Session,
    recovery_user: tuple[str, str, User],
    fake_email_sender,
) -> None:
    login_id, email, _user = recovery_user
    fake_email_sender.fail_next = True

    response = client.post(
        "/api/v1/auth/password-reset/request-code",
        json={"login_id": login_id, "email": email},
    )
    assert response.status_code == 503
    assert _auth_detail(response)["code"] == "AUTH_EMAIL_UNAVAILABLE"

    row = db.scalar(
        select(AuthVerificationCode)
        .where(
            AuthVerificationCode.purpose == "RESET_PASSWORD",
            AuthVerificationCode.email == email,
            AuthVerificationCode.login_id == login_id,
        )
        .order_by(AuthVerificationCode.created_at.desc())
    )
    assert row is not None
    assert row.invalidated_at is not None
