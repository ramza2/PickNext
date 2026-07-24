"""TMDB HTTP client errors (no secrets in messages)."""

from __future__ import annotations


class TmdbError(Exception):
    """Base TMDB integration error."""

    code: str = "TMDB_UPSTREAM_ERROR"

    def __init__(self, message: str = "TMDB request failed") -> None:
        super().__init__(message)
        self.message = message


class TmdbNotConfiguredError(TmdbError):
    code = "TMDB_NOT_CONFIGURED"

    def __init__(self, message: str = "TMDB is not configured") -> None:
        super().__init__(message)


class TmdbAuthFailedError(TmdbError):
    code = "TMDB_AUTH_FAILED"

    def __init__(self, message: str = "TMDB authentication failed") -> None:
        super().__init__(message)


class TmdbNotFoundError(TmdbError):
    code = "TMDB_NOT_FOUND"

    def __init__(self, message: str = "TMDB resource not found") -> None:
        super().__init__(message)


class TmdbRateLimitedError(TmdbError):
    code = "TMDB_RATE_LIMITED"

    def __init__(
        self,
        message: str = "TMDB rate limit exceeded",
        *,
        retry_after: str | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class TmdbUnavailableError(TmdbError):
    code = "TMDB_UNAVAILABLE"

    def __init__(self, message: str = "TMDB is temporarily unavailable") -> None:
        super().__init__(message)


class TmdbUpstreamError(TmdbError):
    code = "TMDB_UPSTREAM_ERROR"

    def __init__(self, message: str = "TMDB upstream error") -> None:
        super().__init__(message)
