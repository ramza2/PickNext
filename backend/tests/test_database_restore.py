"""OPS-1 API gate + restore request validation tests (non-destructive)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.main import create_app
from app.models import User
from app.services import ops_lock


TEST_PASSWORD = "Ops1TestPass!9"


@pytest.fixture(autouse=True)
def _reset_ops_lock():
    ops_lock.release_ops_lock()
    ops_lock.set_maintenance(False)
    yield
    ops_lock.release_ops_lock()
    ops_lock.set_maintenance(False)


def _unique_login(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:10]}"


def _login(client: TestClient, login_id: str, password: str = TEST_PASSWORD) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"login_id": login_id, "password": password, "remember_me": False},
    )
    assert response.status_code == 200, response.text


def test_database_maintenance_status_unauthorized_when_disabled(
    client: TestClient,
    db: Session,
):
    login_id = _unique_login("opsdis")
    user = User(
        email=f"{login_id}@example.com",
        display_name=login_id,
        login_id=login_id,
        password_hash=hash_password(TEST_PASSWORD),
        is_active=True,
    )
    db.add(user)
    db.flush()
    _login(client, login_id)

    # Default settings keep OPS disabled.
    response = client.get("/api/v1/settings/database-maintenance")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["authorized"] is False
    assert body["backup_available"] is False
    assert body["restore_available"] is False


def test_database_backup_forbidden_when_disabled(client: TestClient, db: Session):
    login_id = _unique_login("opsbak")
    user = User(
        email=f"{login_id}@example.com",
        display_name=login_id,
        login_id=login_id,
        password_hash=hash_password(TEST_PASSWORD),
        is_active=True,
    )
    db.add(user)
    db.flush()
    _login(client, login_id)
    response = client.post("/api/v1/settings/database-backup")
    assert response.status_code == 403


def test_restore_execute_rejects_bad_confirmation(client: TestClient, db: Session, monkeypatch):
    login_id = _unique_login("opsex")
    user = User(
        email=f"{login_id}@example.com",
        display_name=login_id,
        login_id=login_id,
        password_hash=hash_password(TEST_PASSWORD),
        is_active=True,
    )
    db.add(user)
    db.flush()

    settings = get_settings()
    monkeypatch.setattr(settings, "ops_database_maintenance_enabled", True)
    monkeypatch.setattr(settings, "ops_maintenance_admin_login_id", login_id)

    # Execute uses SessionLocal (not overridden test db). Ensure user exists in real DB
    # by committing is not allowed in nested transaction tests — instead mock require path.
    # Call endpoint without relying on cutover: confirmation fails first after lock/auth.
    # Because execute opens SessionLocal against real configured DB, user may be absent.
    # So we only assert confirmation validation via service unit path here.
    from app.services import database_maintenance as dm

    with pytest.raises(Exception) as exc:
        dm.execute_restore(
            settings=settings,
            user_id=user.id,
            restore_token="invalid",
            confirmation="wrong",
            current_password=TEST_PASSWORD,
        )
    assert getattr(exc.value, "status_code", None) == 422


def test_load_token_expired(tmp_path, monkeypatch):
    import json
    from fastapi import HTTPException
    from app.services import database_maintenance as dm

    monkeypatch.setattr(dm, "_token_dir", lambda: tmp_path)
    token = "expired-token-value"
    zip_path, meta_path = dm._token_paths(token)
    zip_path.write_bytes(b"zip")
    meta_path.write_text(
        json.dumps(
            {
                "expires_at": "2000-01-01T00:00:00Z",
                "dump_sha256": "abc",
                "used": False,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(HTTPException) as exc:
        dm._load_token(token)
    assert exc.value.status_code == 400


def test_load_token_unknown(tmp_path, monkeypatch):
    from fastapi import HTTPException
    from app.services import database_maintenance as dm

    monkeypatch.setattr(dm, "_token_dir", lambda: tmp_path)
    with pytest.raises(HTTPException) as exc:
        dm._load_token("missing-token")
    assert exc.value.status_code == 400


def test_extract_package_rejects_corrupt_zip():
    from fastapi import HTTPException
    from app.services import database_maintenance as dm

    settings = get_settings()
    with pytest.raises(HTTPException) as exc:
        dm._extract_package(b"not-a-zip", settings)
    assert exc.value.status_code == 400


def test_restore_execute_requires_auth(client: TestClient):
    response = client.post(
        "/api/v1/settings/database-restore/execute",
        json={
            "restore_token": "x",
            "confirmation": "복원",
            "current_password": "pw",
        },
    )
    assert response.status_code == 401


def test_restore_inspect_forbidden_when_disabled(client: TestClient, db: Session):
    login_id = _unique_login("opsins")
    user = User(
        email=f"{login_id}@example.com",
        display_name=login_id,
        login_id=login_id,
        password_hash=hash_password(TEST_PASSWORD),
        is_active=True,
    )
    db.add(user)
    db.flush()
    _login(client, login_id)
    response = client.post(
        "/api/v1/settings/database-restore/inspect",
        files={"file": ("backup.zip", b"PK\x03\x04", "application/zip")},
    )
    assert response.status_code == 403


def test_health_ok_during_maintenance():
    ops_lock.set_maintenance(True, reason="test")
    try:
        app = create_app()
        with TestClient(app) as client:
            response = client.get("/api/v1/health")
            assert response.status_code == 200
            assert response.json() == {"status": "ok", "database": "connected"}
            blocked = client.get("/api/v1/categories")
            assert blocked.status_code == 503
    finally:
        ops_lock.set_maintenance(False)
