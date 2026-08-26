"""OPS-1 PostgreSQL backup / restore maintenance service."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import stat
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
from zipfile import ZipFile, ZipInfo

from fastapi import HTTPException, status
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.security import verify_password
from app.models import User
from app.services import ops_lock

logger = logging.getLogger(__name__)

BACKUP_FORMAT = "picknext-database-backup"
BACKUP_FORMAT_VERSION = 1
CONFIRMATION_TEXT = "복원"
EXCLUDE_TABLE_DATA = ("user_sessions", "auth_verification_codes")
COUNT_TABLES = (
    "users",
    "categories",
    "collections",
    "items",
    "recommendation_history",
    "recommendation_history_items",
)
SAFE_DB_SUFFIX_RE = re.compile(
    r"^.+_(restore_validate|restore_stage|pre_restore|restore_bad)_[a-z0-9]+$",
)
IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
MAX_MANIFEST_BYTES = 256_000
MAX_UNCOMPRESSED_RATIO = 200
MAX_ZIP_ENTRIES = 8


@dataclass
class BackupPackagePaths:
    work_dir: Path
    dump_path: Path
    manifest_path: Path
    zip_path: Path


def require_ops_admin(user: User, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if not settings.ops_database_maintenance_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Database maintenance is disabled",
        )
    admin_id = settings.ops_maintenance_admin_login_id
    if not admin_id or user.login_id != admin_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Database maintenance requires the designated operator",
        )


def _pg_env(settings: Settings) -> dict[str, str]:
    env = os.environ.copy()
    env["PGPASSWORD"] = settings.postgres_password
    env.pop("PGPASSFILE", None)
    return env


def _run_pg(
    args: list[str],
    *,
    settings: Settings,
    timeout: int = 600,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        shell=False,
        check=False,
        capture_output=True,
        text=True,
        env=_pg_env(settings),
        timeout=timeout,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        safe = stderr[:500].replace(settings.postgres_password, "***")
        logger.error("pg tool failed: cmd=%s code=%s err=%s", args[0], completed.returncode, safe)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database maintenance tool failed",
        )
    return completed


def pg_tool_major(binary: str = "pg_dump") -> int:
    completed = subprocess.run(
        [binary, "--version"],
        shell=False,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{binary} is not available",
        )
    match = re.search(r"(\d+)\.", completed.stdout or "")
    if not match:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to parse {binary} version",
        )
    return int(match.group(1))


def postgres_server_major(db: Session) -> int:
    version = db.execute(text("SHOW server_version")).scalar_one()
    match = re.match(r"(\d+)", str(version))
    if not match:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to parse PostgreSQL server version",
        )
    return int(match.group(1))


def alembic_revision(db: Session) -> str:
    value = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    if not value:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="alembic_version is missing",
        )
    return str(value)


def core_counts(db: Session) -> dict[str, int]:
    result: dict[str, int] = {}
    for table in COUNT_TABLES:
        if not IDENT_RE.match(table):
            raise RuntimeError(f"unsafe table name: {table}")
        result[table] = int(db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one())
    return result


def auth_transient_counts(db: Session) -> dict[str, int]:
    return {
        "user_sessions": int(db.execute(text("SELECT COUNT(*) FROM user_sessions")).scalar_one()),
        "auth_verification_codes": int(
            db.execute(text("SELECT COUNT(*) FROM auth_verification_codes")).scalar_one()
        ),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _assert_ident(name: str) -> str:
    if not IDENT_RE.match(name):
        raise RuntimeError(f"unsafe identifier: {name}")
    return name


def _assert_safe_aux_db(name: str) -> str:
    if SAFE_DB_SUFFIX_RE.match(name) or name.startswith("picknext_ops1_test_"):
        return _assert_ident(name)
    raise RuntimeError(f"refusing unsafe database name: {name}")


def _admin_url(settings: Settings, database: str = "postgres") -> URL:
    return URL.create(
        drivername="postgresql+psycopg",
        username=settings.postgres_user,
        password=settings.postgres_password,
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=database,
    )


def _connect_admin(settings: Settings, database: str = "postgres"):
    engine = create_engine(
        _admin_url(settings, database),
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )
    return engine


def _create_database(settings: Settings, name: str) -> None:
    _assert_safe_aux_db(name)
    engine = _connect_admin(settings)
    try:
        with engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": name},
            ).scalar_one_or_none()
            if exists:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Temporary database already exists",
                )
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        engine.dispose()


def _drop_database(settings: Settings, name: str) -> None:
    _assert_safe_aux_db(name)
    engine = _connect_admin(settings)
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": name},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
    finally:
        engine.dispose()


def _rename_database(settings: Settings, from_name: str, to_name: str) -> None:
    _assert_ident(from_name)
    _assert_ident(to_name)
    primary = settings.postgres_db
    if from_name == primary:
        _assert_safe_aux_db(to_name)
    elif to_name == primary:
        _assert_safe_aux_db(from_name)
    else:
        _assert_safe_aux_db(from_name)
        _assert_safe_aux_db(to_name)
    engine = _connect_admin(settings)
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": from_name},
            )
            conn.execute(text(f'ALTER DATABASE "{from_name}" RENAME TO "{to_name}"'))
    finally:
        engine.dispose()


def _dispose_app_pool() -> None:
    from app.db import session as db_session

    db_session.engine.dispose()


def _recreate_app_pool() -> None:
    from app.db import session as db_session

    db_session.engine.dispose()
    db_session.engine = db_session.create_db_engine()
    db_session.SessionLocal = sessionmaker(
        bind=db_session.engine,
        autoflush=False,
        autocommit=False,
        class_=Session,
    )


def _session_on_db(settings: Settings, database: str) -> Session:
    engine = create_engine(_admin_url(settings, database), pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return SessionLocal()


def build_backup_package(
    db: Session,
    settings: Settings,
    *,
    zip_path: Path | None = None,
    keep_dir: Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    work_dir = Path(keep_dir) if keep_dir else Path(tempfile.mkdtemp(prefix="picknext-backup-"))
    work_dir.mkdir(parents=True, exist_ok=True)
    dump_path = work_dir / "database.dump"
    manifest_path = work_dir / "manifest.json"
    out_zip = zip_path or (work_dir / f"picknext-backup-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.zip")

    created_at = datetime.now(timezone.utc)
    pg_major = postgres_server_major(db)
    dump_major = pg_tool_major("pg_dump")
    if pg_major != dump_major:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"pg_dump major {dump_major} does not match server major {pg_major}",
        )
    revision = alembic_revision(db)
    counts = core_counts(db)

    args = [
        "pg_dump",
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        "--host",
        settings.postgres_host,
        "--port",
        str(settings.postgres_port),
        "--username",
        settings.postgres_user,
        "--dbname",
        settings.postgres_db,
        "--file",
        str(dump_path),
    ]
    for table in EXCLUDE_TABLE_DATA:
        args.extend(["--exclude-table-data", table])
    _run_pg(args, settings=settings)

    dump_hash = sha256_file(dump_path)
    manifest = {
        "backup_format": BACKUP_FORMAT,
        "backup_format_version": BACKUP_FORMAT_VERSION,
        "created_at": created_at.isoformat().replace("+00:00", "Z"),
        "postgres_major": pg_major,
        "pg_dump_major": dump_major,
        "alembic_revision": revision,
        "dump_sha256": dump_hash,
        "counts": counts,
        "excluded_table_data": list(EXCLUDE_TABLE_DATA),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    with ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(dump_path, arcname="database.dump")
        zf.write(manifest_path, arcname="manifest.json")

    try:
        os.chmod(out_zip, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass

    return out_zip, manifest


def create_download_backup(db: Session, settings: Settings) -> Path:
    if not ops_lock.try_acquire_ops_lock():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Maintenance busy")
    work_dir: Path | None = None
    try:
        work_dir = Path(tempfile.mkdtemp(prefix="picknext-backup-dl-"))
        zip_path, _ = build_backup_package(db, settings, keep_dir=work_dir)
        return zip_path
    except Exception:
        if work_dir and work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)
        raise
    finally:
        ops_lock.release_ops_lock()


def cleanup_download_dir(zip_path: Path) -> None:
    parent = zip_path.parent
    if parent.exists() and parent.name.startswith("picknext-backup"):
        shutil.rmtree(parent, ignore_errors=True)


def _backup_dir(settings: Settings) -> Path:
    path = Path(settings.ops_backup_dir)
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, stat.S_IRWXU)
    except OSError:
        pass
    return path


def create_safety_backup(db: Session, settings: Settings) -> Path:
    backup_dir = _backup_dir(settings)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffix = secrets.token_hex(3)
    zip_path = backup_dir / f"pre-restore-{stamp}-{suffix}.zip"
    work_dir = Path(tempfile.mkdtemp(prefix="picknext-safety-"))
    try:
        built, _ = build_backup_package(db, settings, zip_path=zip_path, keep_dir=work_dir)
        _apply_retention(backup_dir, settings.ops_backup_retention)
        return built
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _apply_retention(backup_dir: Path, keep: int) -> None:
    files = sorted(
        backup_dir.glob("pre-restore-*.zip"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for stale in files[keep:]:
        try:
            stale.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to remove old safety backup %s", stale.name)


def _validate_zip_members(zf: ZipFile, max_upload: int) -> dict[str, ZipInfo]:
    infos = zf.infolist()
    if len(infos) == 0 or len(infos) > MAX_ZIP_ENTRIES:
        raise HTTPException(status_code=400, detail="Invalid backup package")
    names: dict[str, ZipInfo] = {}
    total_uncompressed = 0
    for info in infos:
        name = info.filename.replace("\\", "/")
        if name.endswith("/"):
            continue
        if name != Path(name).name:
            raise HTTPException(status_code=400, detail="Invalid backup entry path")
        if name in ("", ".", "..") or name.startswith("/") or ".." in name.split("/"):
            raise HTTPException(status_code=400, detail="Invalid backup entry path")
        if info.is_dir():
            continue
        if name in names:
            raise HTTPException(status_code=400, detail="Duplicate backup entry")
        total_uncompressed += max(info.file_size, 0)
        if total_uncompressed > max_upload * MAX_UNCOMPRESSED_RATIO:
            raise HTTPException(status_code=400, detail="Backup package expands too large")
        names[name] = info
    expected = {"manifest.json", "database.dump"}
    if set(names) != expected:
        raise HTTPException(status_code=400, detail="Backup package must contain only manifest.json and database.dump")
    if names["manifest.json"].file_size > MAX_MANIFEST_BYTES:
        raise HTTPException(status_code=400, detail="manifest.json is too large")
    return names


def _extract_package(upload_bytes: bytes, settings: Settings) -> tuple[Path, dict[str, Any], str]:
    if len(upload_bytes) > settings.ops_backup_max_upload_bytes:
        raise HTTPException(status_code=413, detail="Backup file exceeds size limit")
    work_dir = Path(tempfile.mkdtemp(prefix="picknext-restore-pkg-"))
    try:
        zip_path = work_dir / "upload.zip"
        zip_path.write_bytes(upload_bytes)
        with ZipFile(zip_path, "r") as zf:
            _validate_zip_members(zf, settings.ops_backup_max_upload_bytes)
            zf.extract("manifest.json", path=work_dir)
            zf.extract("database.dump", path=work_dir)
        manifest_path = work_dir / "manifest.json"
        dump_path = work_dir / "database.dump"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid manifest.json") from exc
        if not isinstance(manifest, dict):
            raise HTTPException(status_code=400, detail="Invalid manifest.json")
        dump_hash = sha256_file(dump_path)
        return work_dir, manifest, dump_hash
    except HTTPException:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, ValueError) as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="Invalid backup package") from exc
    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise


def _check_manifest_compatibility(
    manifest: dict[str, Any],
    *,
    dump_hash: str,
    current_pg: int,
    current_revision: str,
    restore_major: int,
) -> list[str]:
    warnings: list[str] = []
    if manifest.get("backup_format") != BACKUP_FORMAT:
        raise HTTPException(status_code=422, detail="Unsupported backup format")
    if manifest.get("backup_format_version") != BACKUP_FORMAT_VERSION:
        raise HTTPException(status_code=422, detail="Unsupported backup format version")
    if manifest.get("dump_sha256") != dump_hash:
        raise HTTPException(status_code=422, detail="Backup dump checksum mismatch")
    backup_pg = manifest.get("postgres_major")
    backup_rev = manifest.get("alembic_revision")
    if backup_pg != current_pg:
        raise HTTPException(
            status_code=422,
            detail=f"PostgreSQL major mismatch: backup={backup_pg} current={current_pg}",
        )
    if restore_major != current_pg:
        raise HTTPException(
            status_code=422,
            detail=f"pg_restore major mismatch: tool={restore_major} server={current_pg}",
        )
    if backup_rev != current_revision:
        raise HTTPException(
            status_code=422,
            detail=(
                "현재 PickNext DB Schema와 백업 Schema가 일치하지 않습니다. "
                f"backup={backup_rev} current={current_revision}"
            ),
        )
    return warnings


def _restore_dump_into(settings: Settings, database: str, dump_path: Path) -> None:
    _assert_safe_aux_db(database)
    args = [
        "pg_restore",
        "--no-owner",
        "--no-privileges",
        "--exit-on-error",
        "--host",
        settings.postgres_host,
        "--port",
        str(settings.postgres_port),
        "--username",
        settings.postgres_user,
        "--dbname",
        database,
        str(dump_path),
    ]
    _run_pg(args, settings=settings, timeout=900)


def _validate_restored_db(
    settings: Settings,
    database: str,
    manifest: dict[str, Any],
) -> dict[str, int]:
    session = _session_on_db(settings, database)
    try:
        rev = alembic_revision(session)
        if rev != manifest.get("alembic_revision"):
            raise HTTPException(status_code=422, detail="Restored alembic_version mismatch")
        counts = core_counts(session)
        expected = manifest.get("counts") or {}
        for key, value in counts.items():
            if expected.get(key) != value:
                raise HTTPException(
                    status_code=422,
                    detail=f"Restored count mismatch for {key}",
                )
        return counts
    finally:
        session.close()
        session.bind.dispose()  # type: ignore[union-attr]


def _token_dir() -> Path:
    path = Path(tempfile.gettempdir()) / "picknext-restore"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _token_paths(token: str) -> tuple[Path, Path]:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    base = _token_dir() / digest
    return base.with_suffix(".zip"), base.with_suffix(".meta.json")


def inspect_restore_package(
    db: Session,
    settings: Settings,
    upload_bytes: bytes,
) -> dict[str, Any]:
    if not ops_lock.try_acquire_ops_lock():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Maintenance busy")
    validate_db: str | None = None
    work_dir: Path | None = None
    try:
        current_pg = postgres_server_major(db)
        current_rev = alembic_revision(db)
        restore_major = pg_tool_major("pg_restore")
        work_dir, manifest, dump_hash = _extract_package(upload_bytes, settings)
        try:
            warnings = _check_manifest_compatibility(
                manifest,
                dump_hash=dump_hash,
                current_pg=current_pg,
                current_revision=current_rev,
                restore_major=restore_major,
            )
        except HTTPException as exc:
            if exc.status_code == 422:
                detail = str(exc.detail)
                if "checksum" in detail.lower() or "format" in detail.lower():
                    raise
                return {
                    "restore_token": "",
                    "expires_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "compatible": False,
                    "backup": {
                        "created_at": manifest.get("created_at"),
                        "postgres_major": manifest.get("postgres_major"),
                        "alembic_revision": manifest.get("alembic_revision"),
                        "counts": manifest.get("counts") or {},
                    },
                    "current": {
                        "postgres_major": current_pg,
                        "alembic_revision": current_rev,
                    },
                    "warnings": [detail],
                }
            raise
        # Ensure dump is listable.
        _run_pg(
            ["pg_restore", "--list", str(work_dir / "database.dump")],
            settings=settings,
            timeout=120,
        )
        validate_db = f"{settings.postgres_db}_restore_validate_{secrets.token_hex(4)}"
        _create_database(settings, validate_db)
        _restore_dump_into(settings, validate_db, work_dir / "database.dump")
        counts = _validate_restored_db(settings, validate_db, manifest)

        token = secrets.token_urlsafe(32)
        zip_path, meta_path = _token_paths(token)
        # Persist package for execute.
        shutil.copy2(work_dir / "upload.zip", zip_path)
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=settings.ops_restore_token_ttl_seconds
        )
        meta = {
            "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
            "dump_sha256": dump_hash,
            "manifest": manifest,
            "used": False,
        }
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        try:
            os.chmod(zip_path, stat.S_IRUSR | stat.S_IWUSR)
            os.chmod(meta_path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

        return {
            "restore_token": token,
            "expires_at": meta["expires_at"],
            "compatible": True,
            "backup": {
                "created_at": manifest.get("created_at"),
                "postgres_major": manifest.get("postgres_major"),
                "alembic_revision": manifest.get("alembic_revision"),
                "counts": counts,
            },
            "current": {
                "postgres_major": current_pg,
                "alembic_revision": current_rev,
            },
            "warnings": warnings,
        }
    finally:
        if validate_db:
            try:
                _drop_database(settings, validate_db)
            except Exception:
                logger.exception("Failed to drop validation DB %s", validate_db)
        if work_dir and work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)
        ops_lock.release_ops_lock()


def _load_token(token: str) -> tuple[Path, Path, dict[str, Any]]:
    zip_path, meta_path = _token_paths(token)
    if not zip_path.exists() or not meta_path.exists():
        raise HTTPException(status_code=400, detail="Invalid or expired restore token")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("used"):
        raise HTTPException(status_code=400, detail="Restore token already used")
    expires_at = datetime.fromisoformat(str(meta["expires_at"]).replace("Z", "+00:00"))
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=400, detail="Restore token expired")
    return zip_path, meta_path, meta


def _consume_token(meta_path: Path, zip_path: Path) -> None:
    try:
        meta_path.unlink(missing_ok=True)
        zip_path.unlink(missing_ok=True)
    except OSError:
        pass


def execute_restore(
    *,
    settings: Settings,
    user_id: Any,
    restore_token: str,
    confirmation: str,
    current_password: str,
) -> dict[str, Any]:
    if confirmation != CONFIRMATION_TEXT:
        raise HTTPException(status_code=422, detail="Confirmation text must be exactly '복원'")
    if not current_password:
        raise HTTPException(status_code=401, detail="Password required")

    if not ops_lock.try_acquire_ops_lock():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Maintenance busy")

    stage_db: str | None = None
    old_db: str | None = None
    cutover_started = False
    keep_maintenance = False
    safety_path: Path | None = None

    try:
        # Always resolve SessionLocal via module attribute so post-cutover
        # recreate_app_pool() is visible (avoid stale imported binding).
        from app.db import session as db_session

        auth_db = db_session.SessionLocal()
        try:
            user = auth_db.get(User, user_id)
            if user is None or not user.is_active:
                raise HTTPException(status_code=401, detail="Unauthorized")
            require_ops_admin(user, settings)
            if not verify_password(current_password, user.password_hash):
                raise HTTPException(status_code=401, detail="Password confirmation failed")
            current_pg = postgres_server_major(auth_db)
            current_rev = alembic_revision(auth_db)
        finally:
            auth_db.close()

        zip_path, meta_path, meta = _load_token(restore_token)
        work_dir, manifest, dump_hash = _extract_package(zip_path.read_bytes(), settings)
        try:
            if dump_hash != meta.get("dump_sha256") or dump_hash != manifest.get("dump_sha256"):
                raise HTTPException(status_code=422, detail="Backup dump checksum mismatch")
            restore_major = pg_tool_major("pg_restore")
            _check_manifest_compatibility(
                manifest,
                dump_hash=dump_hash,
                current_pg=current_pg,
                current_revision=current_rev,
                restore_major=restore_major,
            )

            stage_db = f"{settings.postgres_db}_restore_stage_{secrets.token_hex(4)}"
            _create_database(settings, stage_db)
            _restore_dump_into(settings, stage_db, work_dir / "database.dump")
            _validate_restored_db(settings, stage_db, manifest)

            # Safety backup of current DB (before maintenance cutover).
            safety_db = db_session.SessionLocal()
            try:
                safety_path = create_safety_backup(safety_db, settings)
            finally:
                safety_db.close()

            ops_lock.set_maintenance(True, reason="database-restore")
            cutover_started = True
            _dispose_app_pool()

            old_db = f"{settings.postgres_db}_pre_restore_{secrets.token_hex(4)}"
            _assert_safe_aux_db(old_db)
            _rename_database(settings, settings.postgres_db, old_db)
            try:
                # Temporarily allow renaming stage → primary.
                engine = _connect_admin(settings)
                try:
                    with engine.connect() as conn:
                        conn.execute(
                            text(
                                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                                "WHERE datname = :name AND pid <> pg_backend_pid()"
                            ),
                            {"name": stage_db},
                        )
                        conn.execute(
                            text(f'ALTER DATABASE "{stage_db}" RENAME TO "{settings.postgres_db}"')
                        )
                finally:
                    engine.dispose()
                stage_db = None
            except Exception:
                # Roll forward failed — try restore old name.
                try:
                    _rename_database(settings, old_db, settings.postgres_db)
                    old_db = None
                except Exception:
                    logger.critical("CRITICAL: failed to roll back database rename")
                raise

            _recreate_app_pool()
            verify_db = db_session.SessionLocal()
            try:
                counts = core_counts(verify_db)
                expected = manifest.get("counts") or {}
                for key, value in counts.items():
                    if expected.get(key) != value:
                        raise HTTPException(
                            status_code=500,
                            detail=f"Post-restore count mismatch for {key}",
                        )
                if alembic_revision(verify_db) != manifest.get("alembic_revision"):
                    raise HTTPException(status_code=500, detail="Post-restore alembic mismatch")
                transient = auth_transient_counts(verify_db)
                if transient["user_sessions"] != 0 or transient["auth_verification_codes"] != 0:
                    raise HTTPException(
                        status_code=500,
                        detail="Transient auth tables must be empty after restore",
                    )
            except Exception:
                # Post validation failed — swap back.
                logger.exception("Post-restore validation failed; attempting rollback")
                _dispose_app_pool()
                bad_name = f"{settings.postgres_db}_restore_bad_{secrets.token_hex(4)}"
                try:
                    _assert_safe_aux_db(bad_name)
                    _rename_database(settings, settings.postgres_db, bad_name)
                    if old_db:
                        _rename_database(settings, old_db, settings.postgres_db)
                        old_db = None
                    try:
                        _drop_database(settings, bad_name)
                    except Exception:
                        logger.exception("Failed dropping bad restore DB")
                    _recreate_app_pool()
                except Exception:
                    keep_maintenance = True
                    logger.critical(
                        "CRITICAL: automatic DB rollback failed; safety_backup=%s",
                        str(safety_path) if safety_path else None,
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=(
                            "자동 복구에 실패했습니다. "
                            "서버의 사전 백업을 이용한 운영자 복구가 필요합니다."
                        ),
                    ) from None
                raise HTTPException(
                    status_code=500,
                    detail="복원 검증에 실패하여 기존 데이터베이스로 복구했습니다.",
                ) from None
            finally:
                verify_db.close()

            if old_db:
                try:
                    _drop_database(settings, old_db)
                    old_db = None
                except Exception:
                    logger.exception("Failed to drop old DB after successful restore")

            meta["used"] = True
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
            _consume_token(meta_path, zip_path)

            return {
                "status": "restored",
                "require_relogin": True,
                "safety_backup": safety_path.name if safety_path else None,
                "counts": counts,
            }
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)
    finally:
        if stage_db:
            try:
                _drop_database(settings, stage_db)
            except Exception:
                logger.exception("Failed dropping leftover stage DB")
        if not keep_maintenance:
            ops_lock.set_maintenance(False)
            try:
                _recreate_app_pool()
            except Exception:
                logger.exception("Failed recreating app pool after restore")
        ops_lock.release_ops_lock()


def maintenance_status(db: Session, user: User, settings: Settings) -> dict[str, Any]:
    enabled = bool(settings.ops_database_maintenance_enabled)
    authorized = bool(
        enabled
        and settings.ops_maintenance_admin_login_id
        and user.login_id == settings.ops_maintenance_admin_login_id
    )
    payload: dict[str, Any] = {
        "enabled": enabled,
        "authorized": authorized,
        "backup_available": False,
        "restore_available": False,
    }
    if not authorized:
        return payload
    try:
        pg_dump_v = pg_tool_major("pg_dump")
        pg_restore_v = pg_tool_major("pg_restore")
        server_v = postgres_server_major(db)
        tools_ok = pg_dump_v == server_v == pg_restore_v
        payload.update(
            {
                "postgres_major": server_v,
                "alembic_revision": alembic_revision(db),
                "backup_available": tools_ok,
                "restore_available": tools_ok,
                "max_upload_bytes": settings.ops_backup_max_upload_bytes,
            }
        )
    except HTTPException:
        payload["backup_available"] = False
        payload["restore_available"] = False
    return payload
