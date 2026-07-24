"""TMDB integration package."""

from app.integrations.tmdb.client import TmdbClient
from app.integrations.tmdb.errors import (
    TmdbAuthFailedError,
    TmdbError,
    TmdbNotConfiguredError,
    TmdbNotFoundError,
    TmdbRateLimitedError,
    TmdbUnavailableError,
    TmdbUpstreamError,
)

__all__ = [
    "TmdbAuthFailedError",
    "TmdbClient",
    "TmdbError",
    "TmdbNotConfiguredError",
    "TmdbNotFoundError",
    "TmdbRateLimitedError",
    "TmdbUnavailableError",
    "TmdbUpstreamError",
]
