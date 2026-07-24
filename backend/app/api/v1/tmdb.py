"""TMDB read APIs: status, search, details."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.integrations.tmdb.errors import (
    TmdbAuthFailedError,
    TmdbError,
    TmdbNotConfiguredError,
    TmdbNotFoundError,
    TmdbRateLimitedError,
    TmdbUnavailableError,
    TmdbUpstreamError,
)
from app.models import User
from app.schemas.tmdb import (
    TmdbDetailResponse,
    TmdbSearchMediaFilter,
    TmdbSearchResponse,
    TmdbStatusResponse,
)
from app.services.tmdb_service import MAX_QUERY_LENGTH, TmdbService, trim_search_query

router = APIRouter(prefix="/tmdb", tags=["TMDB"])


def get_tmdb_service(request: Request) -> TmdbService:
    service = getattr(request.app.state, "tmdb_service", None)
    if service is None:
        raise HTTPException(status_code=500, detail="TMDB service is not initialized")
    return service


def _raise_tmdb_http(exc: TmdbError) -> None:
    if isinstance(exc, TmdbNotConfiguredError):
        raise HTTPException(status_code=503, detail=exc.code) from exc
    if isinstance(exc, TmdbAuthFailedError):
        raise HTTPException(status_code=503, detail=exc.code) from exc
    if isinstance(exc, TmdbNotFoundError):
        raise HTTPException(status_code=404, detail=exc.code) from exc
    if isinstance(exc, TmdbRateLimitedError):
        headers = {}
        if exc.retry_after:
            headers["Retry-After"] = exc.retry_after
        raise HTTPException(
            status_code=429,
            detail=exc.code,
            headers=headers or None,
        ) from exc
    if isinstance(exc, TmdbUnavailableError):
        raise HTTPException(status_code=503, detail=exc.code) from exc
    if isinstance(exc, TmdbUpstreamError):
        raise HTTPException(status_code=502, detail=exc.code) from exc
    raise HTTPException(status_code=502, detail=exc.code) from exc


@router.get("/status", response_model=TmdbStatusResponse)
async def tmdb_status(
    service: Annotated[TmdbService, Depends(get_tmdb_service)],
) -> TmdbStatusResponse:
    return await service.status()


@router.get("/search", response_model=TmdbSearchResponse)
async def tmdb_search(
    service: Annotated[TmdbService, Depends(get_tmdb_service)],
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    query: str = Query(..., min_length=1, max_length=MAX_QUERY_LENGTH),
    media_type: TmdbSearchMediaFilter = Query(default="all"),
    page: int = Query(default=1, ge=1),
) -> TmdbSearchResponse:
    trimmed = trim_search_query(query)
    if not trimmed:
        raise HTTPException(status_code=422, detail="query must not be blank")
    if len(trimmed) > MAX_QUERY_LENGTH:
        raise HTTPException(status_code=422, detail="query is too long")
    try:
        return await service.search(
            db=db,
            user=user,
            query=trimmed,
            media_type=media_type,
            page=page,
        )
    except TmdbError as exc:
        _raise_tmdb_http(exc)


@router.get(
    "/details/{media_type}/{tmdb_id}",
    response_model=TmdbDetailResponse,
)
async def tmdb_details(
    service: Annotated[TmdbService, Depends(get_tmdb_service)],
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    media_type: Literal["movie", "tv"] = Path(...),
    tmdb_id: int = Path(..., ge=1),
) -> TmdbDetailResponse:
    try:
        return await service.details(
            db=db,
            user=user,
            media_type=media_type,
            tmdb_id=tmdb_id,
        )
    except TmdbError as exc:
        _raise_tmdb_http(exc)
