"""OPS-1 unit tests: zip/manifest validation, admin gate, pg command safety."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.core.security import hash_password
from app.models import User
from app.services import database_maintenance as dm
from app.services import ops_lock


@pytest.fixture(autouse=True)
def _reset_ops_lock():
    ops_lock.release_ops_lock()
    ops_lock.set_maintenance(False)
    yield
    ops_lock.release_ops_lock()
    ops_lock.set_maintenance(False)


def _settings(**overrides) -> Settings:
    base = {
        "_env_file": None,
        "ops_database_maintenance_enabled": True,
        "ops_maintenance_admin_login_id": "opsadmin",
        "ops_backup_max_upload_bytes": 1_048_576,
        "ops_backup_retention": 5,
        "ops_restore_token_ttl_seconds": 900,
        "postgres_host": "localhost",
        "postgres_port": 5432,
        "postgres_user": "picknext",
        "postgres_password": "secret-password",
        "postgres_db": "picknext_ops1_test_unit",
        "auth_code_pepper": "test-auth-code-pepper-not-for-production",
    }
    base.update(overrides)
    return Settings(**base)


def _admin_user() -> User:
    return User(
        email="ops@example.com",
        display_name="Ops",
        login_id="opsadmin",
        password_hash=hash_password("password123"),
        is_active=True,
    )


def _make_zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_require_ops_admin_disabled():
    user = _admin_user()
    with pytest.raises(HTTPException) as exc:
        dm.require_ops_admin(user, _settings(ops_database_maintenance_enabled=False))
    assert exc.value.status_code == 403


def test_require_ops_admin_wrong_login():
    user = _admin_user()
    user.login_id = "someoneelse"
    with pytest.raises(HTTPException) as exc:
        dm.require_ops_admin(user, _settings())
    assert exc.value.status_code == 403


def test_require_ops_admin_ok():
    dm.require_ops_admin(_admin_user(), _settings())


def test_assert_safe_aux_db_rejects_primary():
    with pytest.raises(RuntimeError):
        dm._assert_safe_aux_db("picknext")
    with pytest.raises(RuntimeError):
        dm._assert_safe_aux_db("postgres")


def test_assert_safe_aux_db_allows_known_suffixes():
    dm._assert_safe_aux_db("picknext_ops1_test_target_restore_validate_ab12")
    dm._assert_safe_aux_db("picknext_ops1_test_source_restore_stage_cd34")
    dm._assert_safe_aux_db("picknext_ops1_test_x_pre_restore_ef56")
    dm._assert_safe_aux_db("picknext_ops1_test_x_restore_bad_9900")
    dm._assert_safe_aux_db("picknext_ops1_test_isolated")


def test_validate_zip_ok():
    raw = _make_zip(
        {
            "manifest.json": b'{"ok":true}',
            "database.dump": b"PGDUMP",
        }
    )
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = dm._validate_zip_members(zf, 1_048_576)
    assert set(names) == {"manifest.json", "database.dump"}


@pytest.mark.parametrize(
    "entries",
    [
        {"manifest.json": b"{}"},
        {"manifest.json": b"{}", "database.dump": b"x", "extra.txt": b"no"},
        {"../manifest.json": b"{}", "database.dump": b"x"},
        {"manifest.json": b"{}", "database.dump": b"x", "subdir/database.dump": b"y"},
    ],
)
def test_validate_zip_rejects_bad_packages(entries):
    # Path traversal names may fail at ZipInfo construction differently; wrap.
    try:
        raw = _make_zip(entries)
    except ValueError:
        return
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        with pytest.raises(HTTPException) as exc:
            dm._validate_zip_members(zf, 1_048_576)
    assert exc.value.status_code == 400


def test_validate_zip_rejects_duplicate_entries():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", b"{}")
        zf.writestr("database.dump", b"a")
        # Force a second manifest entry via ZipInfo
        info = zipfile.ZipInfo("manifest.json")
        zf.writestr(info, b"{}")
    with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as zf:
        with pytest.raises(HTTPException) as exc:
            dm._validate_zip_members(zf, 1_048_576)
    assert exc.value.status_code == 400


def test_check_manifest_compatibility_ok():
    manifest = {
        "backup_format": dm.BACKUP_FORMAT,
        "backup_format_version": dm.BACKUP_FORMAT_VERSION,
        "dump_sha256": "abc",
        "postgres_major": 16,
        "alembic_revision": "0007_add_auth_tables",
    }
    warnings = dm._check_manifest_compatibility(
        manifest,
        dump_hash="abc",
        current_pg=16,
        current_revision="0007_add_auth_tables",
        restore_major=16,
    )
    assert warnings == []


@pytest.mark.parametrize(
    "patch_manifest,kwargs,status",
    [
        ({"backup_format": "other"}, {}, 422),
        ({"backup_format_version": 99}, {}, 422),
        ({}, {"dump_hash": "nope"}, 422),
        ({"postgres_major": 15}, {}, 422),
        ({"alembic_revision": "0006"}, {}, 422),
        ({}, {"restore_major": 15}, 422),
    ],
)
def test_check_manifest_compatibility_rejects(patch_manifest, kwargs, status):
    manifest = {
        "backup_format": dm.BACKUP_FORMAT,
        "backup_format_version": dm.BACKUP_FORMAT_VERSION,
        "dump_sha256": "abc",
        "postgres_major": 16,
        "alembic_revision": "0007_add_auth_tables",
    }
    manifest.update(patch_manifest)
    call = {
        "dump_hash": "abc",
        "current_pg": 16,
        "current_revision": "0007_add_auth_tables",
        "restore_major": 16,
    }
    call.update(kwargs)
    with pytest.raises(HTTPException) as exc:
        dm._check_manifest_compatibility(manifest, **call)
    assert exc.value.status_code == status


def test_run_pg_uses_shell_false_and_pgpassword_env():
    settings = _settings()
    completed = MagicMock()
    completed.returncode = 0
    completed.stderr = ""
    with patch("app.services.database_maintenance.subprocess.run", return_value=completed) as run:
        dm._run_pg(["pg_dump", "--format=custom", "--dbname", "db"], settings=settings)
    args, kwargs = run.call_args
    assert args[0][0] == "pg_dump"
    assert kwargs["shell"] is False
    assert "secret-password" not in args[0]
    assert kwargs["env"]["PGPASSWORD"] == "secret-password"


def test_build_backup_excludes_session_tables_in_args(tmp_path: Path):
    settings = _settings()
    db = MagicMock()
    with (
        patch.object(dm, "postgres_server_major", return_value=16),
        patch.object(dm, "pg_tool_major", return_value=16),
        patch.object(dm, "alembic_revision", return_value="0007_add_auth_tables"),
        patch.object(dm, "core_counts", return_value={t: 0 for t in dm.COUNT_TABLES}),
        patch.object(dm, "_run_pg") as run_pg,
        patch.object(dm, "sha256_file", return_value="deadbeef"),
    ):
        # Create empty dump file that build expects after _run_pg
        def _fake_run(args, **_kwargs):
            Path(args[args.index("--file") + 1]).write_bytes(b"DUMP")

        run_pg.side_effect = _fake_run
        zip_path, manifest = dm.build_backup_package(
            db,
            settings,
            zip_path=tmp_path / "out.zip",
            keep_dir=tmp_path / "work",
        )
    assert zip_path.exists()
    called_args = run_pg.call_args[0][0]
    assert called_args[0] == "pg_dump"
    assert "--format=custom" in called_args
    assert "user_sessions" in called_args
    assert "auth_verification_codes" in called_args
    assert settings.postgres_password not in called_args
    with zipfile.ZipFile(zip_path) as zf:
        assert set(zf.namelist()) == {"manifest.json", "database.dump"}
    assert manifest["dump_sha256"] == "deadbeef"


def test_retention_only_touches_pre_restore(tmp_path: Path):
    keep = tmp_path / "pre-restore-20260101-000001-aaaaaa.zip"
    drop = tmp_path / "pre-restore-20260101-000000-bbbbbb.zip"
    manual = tmp_path / "manual-backup.zip"
    for path in (keep, drop, manual):
        path.write_bytes(b"x")
        # Ensure mtime order: drop older
    import os
    import time

    older = time.time() - 100
    newer = time.time() - 10
    os.utime(drop, (older, older))
    os.utime(keep, (newer, newer))
    os.utime(manual, (newer, newer))
    dm._apply_retention(tmp_path, keep=1)
    assert keep.exists()
    assert not drop.exists()
    assert manual.exists()


def test_create_download_backup_conflict():
    assert ops_lock.try_acquire_ops_lock()
    try:
        with pytest.raises(HTTPException) as exc:
            dm.create_download_backup(MagicMock(), _settings())
        assert exc.value.status_code == 409
    finally:
        ops_lock.release_ops_lock()


def test_pg_dump_args_exclude_table_data_flag_name():
    # PostgreSQL 16 accepts --exclude-table-data=table or as two args.
    assert "user_sessions" in dm.EXCLUDE_TABLE_DATA
    assert "auth_verification_codes" in dm.EXCLUDE_TABLE_DATA


def test_pg_client_major_when_available():
    import shutil

    if shutil.which("pg_dump") is None or shutil.which("pg_restore") is None:
        pytest.skip("pg_dump/pg_restore not on PATH")
    assert dm.pg_tool_major("pg_dump") == 16
    assert dm.pg_tool_major("pg_restore") == 16


def test_maintenance_status_hides_details_for_non_admin(db):
    settings = _settings()
    user = User(
        email="x@example.com",
        display_name="x",
        login_id="notadmin",
        password_hash="h",
        is_active=True,
    )
    payload = dm.maintenance_status(db, user, settings)
    assert payload["enabled"] is True
    assert payload["authorized"] is False
    assert "postgres_major" not in payload or payload.get("postgres_major") is None
    assert payload["backup_available"] is False
