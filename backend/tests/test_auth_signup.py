"""Signup request-code and complete flow tests (AUTH-1)."""

from __future__ import annotations

import re
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuthVerificationCode, Category, User
from app.services.seed import DEFAULT_CATEGORIES

TEST_PASSWORD = "test-password-ok"


def _auth_detail(resp) -> dict:
    detail = resp.json()["detail"]
    return detail if isinstance(detail, dict) else {"code": detail}


def _unique_login_id() -> str:
    return f"user{uuid4().hex[:8]}"


def _unique_email(login_id: str) -> str:
    return f"{login_id}@example.com"


def _extract_verification_code(body_text: str) -> str:
    match = re.search(r"\b(\d{6})\b", body_text)
    assert match is not None, f"6-digit code not found in email body: {body_text!r}"
    return match.group(1)


def _request_signup_code(
    client: TestClient,
    *,
    login_id: str,
    email: str,
) -> None:
    response = client.post(
        "/api/v1/auth/signup/request-code",
        json={"login_id": login_id, "email": email},
    )
    assert response.status_code == 200
    assert response.json()["message"]


def _complete_signup(
    client: TestClient,
    *,
    login_id: str,
    email: str,
    verification_code: str,
) -> dict:
    response = client.post(
        "/api/v1/auth/signup/complete",
        json={
            "login_id": login_id,
            "email": email,
            "verification_code": verification_code,
            "password": TEST_PASSWORD,
            "password_confirm": TEST_PASSWORD,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_signup_request_code_sends_email_and_hashes_code(
    client: TestClient,
    db: Session,
    fake_email_sender,
) -> None:
    login_id = _unique_login_id()
    email = _unique_email(login_id)

    _request_signup_code(client, login_id=login_id, email=email)

    assert len(fake_email_sender.messages) == 1
    message = fake_email_sender.messages[-1]
    assert message.to_email == email
    raw_code = _extract_verification_code(message.body_text)

    row = db.scalar(
        select(AuthVerificationCode)
        .where(
            AuthVerificationCode.purpose == "SIGNUP",
            AuthVerificationCode.email == email,
            AuthVerificationCode.login_id == login_id,
        )
        .order_by(AuthVerificationCode.created_at.desc())
    )
    assert row is not None
    assert row.code_hash != raw_code
    assert len(row.code_hash) == 64
    assert raw_code not in row.code_hash


def test_signup_complete_creates_user_with_defaults(
    client: TestClient,
    db: Session,
    fake_email_sender,
) -> None:
    login_id = _unique_login_id()
    email = _unique_email(login_id)

    _request_signup_code(client, login_id=login_id, email=email)
    code = _extract_verification_code(fake_email_sender.messages[-1].body_text)

    body = _complete_signup(
        client,
        login_id=login_id,
        email=email,
        verification_code=code,
    )
    assert body["login_id"] == login_id
    assert body["email"] == email

    user = db.scalar(select(User).where(User.login_id == login_id))
    assert user is not None
    assert user.display_name == login_id
    assert user.email_verified_at is not None
    assert user.password_hash.startswith("$argon2")
    from app.core.security import verify_password

    assert verify_password(TEST_PASSWORD, user.password_hash) is True

    category_count = db.scalar(
        select(func.count()).select_from(Category).where(Category.user_id == user.id)
    )
    assert category_count == len(DEFAULT_CATEGORIES)


def test_signup_duplicate_login_id_rejected(
    client: TestClient,
    db: Session,
    fake_email_sender,
) -> None:
    login_id = _unique_login_id()
    email_a = _unique_email(login_id)
    email_b = f"b-{uuid4().hex[:8]}@example.com"

    _request_signup_code(client, login_id=login_id, email=email_a)
    code = _extract_verification_code(fake_email_sender.messages[-1].body_text)
    _complete_signup(
        client,
        login_id=login_id,
        email=email_a,
        verification_code=code,
    )

    response = client.post(
        "/api/v1/auth/signup/request-code",
        json={"login_id": login_id, "email": email_b},
    )
    assert response.status_code == 400
    assert _auth_detail(response)["code"] == "AUTH_LOGIN_ID_TAKEN"


def test_signup_duplicate_email_rejected(
    client: TestClient,
    db: Session,
    fake_email_sender,
) -> None:
    login_id_a = _unique_login_id()
    login_id_b = _unique_login_id()
    email = _unique_email(login_id_a)

    _request_signup_code(client, login_id=login_id_a, email=email)
    code = _extract_verification_code(fake_email_sender.messages[-1].body_text)
    _complete_signup(
        client,
        login_id=login_id_a,
        email=email,
        verification_code=code,
    )

    response = client.post(
        "/api/v1/auth/signup/request-code",
        json={"login_id": login_id_b, "email": email},
    )
    assert response.status_code == 400
    assert _auth_detail(response)["code"] == "AUTH_EMAIL_TAKEN"


def test_signup_wrong_verification_code_rejected(
    client: TestClient,
    fake_email_sender,
) -> None:
    login_id = _unique_login_id()
    email = _unique_email(login_id)

    _request_signup_code(client, login_id=login_id, email=email)

    response = client.post(
        "/api/v1/auth/signup/complete",
        json={
            "login_id": login_id,
            "email": email,
            "verification_code": "000000",
            "password": TEST_PASSWORD,
            "password_confirm": TEST_PASSWORD,
        },
    )
    assert response.status_code == 400
    assert _auth_detail(response)["code"] == "AUTH_CODE_INVALID"


def test_signup_reuse_consumed_code_rejected(
    client: TestClient,
    fake_email_sender,
) -> None:
    login_id = _unique_login_id()
    email = _unique_email(login_id)

    _request_signup_code(client, login_id=login_id, email=email)
    code = _extract_verification_code(fake_email_sender.messages[-1].body_text)
    _complete_signup(
        client,
        login_id=login_id,
        email=email,
        verification_code=code,
    )

    response = client.post(
        "/api/v1/auth/signup/complete",
        json={
            "login_id": login_id,
            "email": email,
            "verification_code": code,
            "password": TEST_PASSWORD,
            "password_confirm": TEST_PASSWORD,
        },
    )
    assert response.status_code == 400
    assert _auth_detail(response)["code"] == "AUTH_CODE_INVALID"


def test_signup_request_code_email_unavailable(
    client: TestClient,
    db: Session,
    fake_email_sender,
) -> None:
    login_id = _unique_login_id()
    email = _unique_email(login_id)
    fake_email_sender.fail_next = True

    response = client.post(
        "/api/v1/auth/signup/request-code",
        json={"login_id": login_id, "email": email},
    )
    assert response.status_code == 503
    assert _auth_detail(response)["code"] == "AUTH_EMAIL_UNAVAILABLE"

    row = db.scalar(
        select(AuthVerificationCode)
        .where(
            AuthVerificationCode.purpose == "SIGNUP",
            AuthVerificationCode.email == email,
        )
        .order_by(AuthVerificationCode.created_at.desc())
    )
    assert row is not None
    assert row.invalidated_at is not None
