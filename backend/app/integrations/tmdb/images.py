"""Pure TMDB image URL builders (no network, no secrets).

Item API responses must not call TMDB `/configuration` per row.
Uses the stable public image host and configured size preferences.
"""

from __future__ import annotations

from app.core.config import Settings, get_settings

EXTERNAL_SOURCE_TMDB = "tmdb"
TMDB_SECURE_IMAGE_BASE = "https://image.tmdb.org/t/p/"


def normalize_tmdb_file_path(path: str | None) -> str | None:
    if path is None or not isinstance(path, str):
        return None
    trimmed = path.strip()
    if not trimmed:
        return None
    if not trimmed.startswith("/"):
        trimmed = f"/{trimmed}"
    # Reject obvious non-relative values (full URLs, schemes).
    if "://" in trimmed or trimmed.startswith("//"):
        return None
    return trimmed


def build_tmdb_image_url(path: str | None, *, size: str) -> str | None:
    file_path = normalize_tmdb_file_path(path)
    if file_path is None:
        return None
    size_token = (size or "").strip().strip("/")
    if not size_token:
        return None
    base = TMDB_SECURE_IMAGE_BASE
    return f"{base}{size_token}{file_path}"


def build_tmdb_poster_url(
    path: str | None,
    *,
    settings: Settings | None = None,
) -> str | None:
    cfg = settings or get_settings()
    return build_tmdb_image_url(path, size=cfg.tmdb_poster_size)


def build_tmdb_backdrop_url(
    path: str | None,
    *,
    settings: Settings | None = None,
) -> str | None:
    cfg = settings or get_settings()
    return build_tmdb_image_url(path, size=cfg.tmdb_backdrop_size)


def item_poster_url(
    *,
    external_source: str | None,
    poster_path: str | None,
    settings: Settings | None = None,
) -> str | None:
    if external_source != EXTERNAL_SOURCE_TMDB:
        return None
    return build_tmdb_poster_url(poster_path, settings=settings)


def item_backdrop_url(
    *,
    external_source: str | None,
    backdrop_path: str | None,
    settings: Settings | None = None,
) -> str | None:
    if external_source != EXTERNAL_SOURCE_TMDB:
        return None
    return build_tmdb_backdrop_url(backdrop_path, settings=settings)
