"""OPS-1 database maintenance API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import SessionLocal, get_db
from app.models import User
from app.services import database_maintenance as maintenance
from app.services import session_service

router = APIRouter(prefix="/settings", tags=["settings"])


class DatabaseMaintenanceStatusResponse(BaseModel):
    enabled: bool
    authorized: bool
    postgres_major: int | None = None
    alembic_revision: str | None = None
    backup_available: bool
    restore_available: bool
    max_upload_bytes: int | None = None


class RestoreInspectResponse(BaseModel):
    restore_token: str
    expires_at: str
    compatible: bool
    backup: dict[str, Any]
    current: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


class RestoreExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    restore_token: str
    confirmation: str
    current_password: str


class RestoreExecuteResponse(BaseModel):
    status: str
    require_relogin: bool
    safety_backup: str | None = None
    counts: dict[str, int] | None = None


def _resolve_user_brief(request: Request, settings: Settings) -> User:
    """Load current user then close the DB session before cutover-sensitive work."""
    raw = request.cookies.get(settings.auth_cookie_name)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    db = SessionLocal()
    try:
        session = session_service.get_active_session_for_token(db, raw_token=raw)
        if session is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        user = db.get(User, session.user_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        # Detach fields we need after close.
        db.expunge(user)
        return user
    finally:
        db.close()


@router.get("/database-maintenance", response_model=DatabaseMaintenanceStatusResponse)
def read_database_maintenance_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> DatabaseMaintenanceStatusResponse:
    return DatabaseMaintenanceStatusResponse(**maintenance.maintenance_status(db, user, settings))


@router.post("/database-backup")
def create_database_backup(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    maintenance.require_ops_admin(user, settings)
    zip_path = maintenance.create_download_backup(db, settings)
    filename = zip_path.name

    def _cleanup() -> None:
        maintenance.cleanup_download_dir(Path(zip_path))

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=filename,
        background=BackgroundTask(_cleanup),
    )


@router.post(
    "/database-restore/inspect",
    response_model=RestoreInspectResponse,
)
async def inspect_database_restore(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> RestoreInspectResponse:
    maintenance.require_ops_admin(user, settings)
    raw = await file.read()
    if len(raw) > settings.ops_backup_max_upload_bytes:
        raise HTTPException(status_code=413, detail="Backup file exceeds size limit")
    payload = maintenance.inspect_restore_package(db, settings, raw)
    return RestoreInspectResponse(**payload)


@router.post(
    "/database-restore/execute",
    response_model=RestoreExecuteResponse,
)
def execute_database_restore(
    request: Request,
    payload: RestoreExecuteRequest,
    settings: Settings = Depends(get_settings),
) -> RestoreExecuteResponse:
    user = _resolve_user_brief(request, settings)
    maintenance.require_ops_admin(user, settings)
    result = maintenance.execute_restore(
        settings=settings,
        user_id=user.id,
        restore_token=payload.restore_token,
        confirmation=payload.confirmation,
        current_password=payload.current_password,
    )
    return RestoreExecuteResponse(**result)
