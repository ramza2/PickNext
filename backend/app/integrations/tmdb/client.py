"""Async TMDB HTTP client. Never logs secrets or full upstream bodies."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
from urllib.parse import urljoin

import httpx

from app.core.config import Settings
from app.integrations.tmdb.errors import (
    TmdbAuthFailedError,
    TmdbError,
    TmdbNotConfiguredError,
    TmdbNotFoundError,
    TmdbRateLimitedError,
    TmdbUnavailableError,
    TmdbUpstreamError,
)

logger = logging.getLogger(__name__)

# include_adult is fixed product policy — never taken from env or clients.
INCLUDE_ADULT = True


class TmdbClient:
    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient,
    ) -> None:
        self._settings = settings
        self._http = http_client
        self._config_lock = asyncio.Lock()
        self._config_payload: dict[str, Any] | None = None
        self._config_expires_at: float = 0.0
        self._status_lock = asyncio.Lock()
        self._status_payload: dict[str, Any] | None = None
        self._status_expires_at: float = 0.0

    @property
    def auth_mode(self) -> str:
        return self._settings.tmdb_auth_mode

    def require_configured(self) -> None:
        if self.auth_mode == "none":
            raise TmdbNotConfiguredError()

    def _auth_headers_and_params(self) -> tuple[dict[str, str], dict[str, str]]:
        self.require_configured()
        headers = {"Accept": "application/json"}
        params: dict[str, str] = {
            "language": self._settings.tmdb_language,
        }
        mode = self.auth_mode
        if mode == "bearer":
            token = self._settings.tmdb_api_read_access_token
            assert token is not None
            headers["Authorization"] = f"Bearer {token.get_secret_value().strip()}"
        elif mode == "api_key":
            key = self._settings.tmdb_api_key
            assert key is not None
            params["api_key"] = key.get_secret_value().strip()
        return headers, params

    def _url(self, path: str) -> str:
        base = self._settings.tmdb_api_base_url.rstrip("/") + "/"
        return urljoin(base, path.lstrip("/"))

    async def get_json(
        self,
        path: str,
        *,
        extra_params: dict[str, str | int | bool] | None = None,
        allow_retry: bool = True,
    ) -> dict[str, Any]:
        headers, params = self._auth_headers_and_params()
        if extra_params:
            for key, value in extra_params.items():
                if isinstance(value, bool):
                    params[key] = "true" if value else "false"
                else:
                    params[key] = str(value)

        url = self._url(path)
        started = time.perf_counter()
        try:
            response = await self._http.get(
                url,
                headers=headers,
                params=params,
                timeout=self._settings.tmdb_request_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            logger.warning(
                "tmdb timeout path=%s auth_mode=%s",
                path,
                self.auth_mode,
            )
            if allow_retry:
                await asyncio.sleep(0.2)
                return await self.get_json(
                    path,
                    extra_params=extra_params,
                    allow_retry=False,
                )
            raise TmdbUnavailableError() from exc
        except httpx.HTTPError as exc:
            logger.warning(
                "tmdb connection error path=%s auth_mode=%s err_type=%s",
                path,
                self.auth_mode,
                type(exc).__name__,
            )
            raise TmdbUnavailableError() from exc

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        status = response.status_code
        logger.info(
            "tmdb GET path=%s status=%s elapsed_ms=%s auth_mode=%s",
            path,
            status,
            elapsed_ms,
            self.auth_mode,
        )

        if status == 401 or status == 403:
            raise TmdbAuthFailedError()
        if status == 404:
            raise TmdbNotFoundError()
        if status == 429:
            raise TmdbRateLimitedError(
                retry_after=response.headers.get("Retry-After"),
            )
        if status >= 500:
            if allow_retry:
                await asyncio.sleep(0.2)
                return await self.get_json(
                    path,
                    extra_params=extra_params,
                    allow_retry=False,
                )
            raise TmdbUpstreamError()
        if status >= 400:
            raise TmdbUpstreamError()

        try:
            payload = response.json()
        except ValueError as exc:
            raise TmdbUpstreamError("TMDB returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise TmdbUpstreamError("TMDB returned unexpected JSON")
        return payload

    async def get_configuration(self, *, force: bool = False) -> dict[str, Any]:
        now = time.monotonic()
        if (
            not force
            and self._config_payload is not None
            and now < self._config_expires_at
        ):
            return self._config_payload

        async with self._config_lock:
            now = time.monotonic()
            if (
                not force
                and self._config_payload is not None
                and now < self._config_expires_at
            ):
                return self._config_payload
            payload = await self.get_json("/configuration")
            self._config_payload = payload
            self._config_expires_at = (
                now + float(self._settings.tmdb_configuration_ttl_seconds)
            )
            return payload

    async def probe_status(self, *, force: bool = False) -> dict[str, Any]:
        """Return a short-lived status snapshot without secrets."""
        now = time.monotonic()
        if (
            not force
            and self._status_payload is not None
            and now < self._status_expires_at
        ):
            return self._status_payload

        async with self._status_lock:
            now = time.monotonic()
            if (
                not force
                and self._status_payload is not None
                and now < self._status_expires_at
            ):
                return self._status_payload

            mode = self.auth_mode
            checked_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            base = {
                "auth_mode": mode,
                "language": self._settings.tmdb_language,
                "region": self._settings.tmdb_region,
                "checked_at": checked_at,
            }
            if mode == "none":
                payload = {
                    **base,
                    "status": "NOT_CONFIGURED",
                    "configured": False,
                    "available": False,
                }
            else:
                try:
                    await self.get_configuration(force=force)
                    payload = {
                        **base,
                        "status": "AVAILABLE",
                        "configured": True,
                        "available": True,
                    }
                except TmdbError:
                    payload = {
                        **base,
                        "status": "UNAVAILABLE",
                        "configured": True,
                        "available": False,
                    }

            self._status_payload = payload
            self._status_expires_at = (
                now + float(self._settings.tmdb_status_ttl_seconds)
            )
            return payload

    async def search_movie(self, *, query: str, page: int) -> dict[str, Any]:
        return await self.get_json(
            "/search/movie",
            extra_params={
                "query": query,
                "page": page,
                "include_adult": INCLUDE_ADULT,
                "region": self._settings.tmdb_region,
            },
        )

    async def search_tv(self, *, query: str, page: int) -> dict[str, Any]:
        return await self.get_json(
            "/search/tv",
            extra_params={
                "query": query,
                "page": page,
                "include_adult": INCLUDE_ADULT,
            },
        )

    async def search_multi(self, *, query: str, page: int) -> dict[str, Any]:
        # /search/multi does not document a region parameter — do not invent one.
        return await self.get_json(
            "/search/multi",
            extra_params={
                "query": query,
                "page": page,
                "include_adult": INCLUDE_ADULT,
            },
        )

    async def movie_details(self, tmdb_id: int) -> dict[str, Any]:
        return await self.get_json(
            f"/movie/{tmdb_id}",
            extra_params={"append_to_response": "credits,external_ids"},
        )

    async def tv_details(self, tmdb_id: int) -> dict[str, Any]:
        return await self.get_json(
            f"/tv/{tmdb_id}",
            extra_params={"append_to_response": "credits,external_ids"},
        )
