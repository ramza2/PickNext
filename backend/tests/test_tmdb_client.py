"""TMDB client auth, search params, and error mapping (mocked HTTP)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.integrations.tmdb.client import INCLUDE_ADULT, TmdbClient
from app.integrations.tmdb.errors import (
    TmdbAuthFailedError,
    TmdbNotConfiguredError,
    TmdbNotFoundError,
    TmdbRateLimitedError,
    TmdbUnavailableError,
    TmdbUpstreamError,
)


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "_env_file": None,
        "tmdb_api_key": None,
        "tmdb_api_read_access_token": None,
        "tmdb_language": "ko-KR",
        "tmdb_region": "KR",
        "tmdb_api_base_url": "https://api.themoviedb.org/3",
        "tmdb_request_timeout_seconds": 2.0,
        "tmdb_configuration_ttl_seconds": 86400,
        "tmdb_status_ttl_seconds": 60,
    }
    base.update(overrides)
    return Settings(**base)


CONFIGURATION = {
    "images": {
        "secure_base_url": "https://image.tmdb.org/t/p/",
        "poster_sizes": ["w92", "w500", "original"],
        "backdrop_sizes": ["w300", "w780", "original"],
        "profile_sizes": ["w45", "w185", "original"],
    }
}


def _handler_factory(
    recorded: list[httpx.Request],
    responses: dict[str, httpx.Response] | None = None,
    default_status: int = 200,
    default_json: dict[str, Any] | None = None,
):
    responses = responses or {}

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        path = request.url.path
        if path in responses:
            return responses[path]
        body = default_json if default_json is not None else {"ok": True}
        return httpx.Response(default_status, json=body)

    return handler


@pytest.mark.asyncio
async def test_bearer_preferred_over_api_key() -> None:
    recorded: list[httpx.Request] = []
    transport = httpx.MockTransport(_handler_factory(recorded, default_json=CONFIGURATION))
    settings = _settings(
        tmdb_api_read_access_token=SecretStr("token-secret"),
        tmdb_api_key=SecretStr("key-secret"),
    )
    async with httpx.AsyncClient(transport=transport) as http:
        client = TmdbClient(settings, http)
        await client.get_configuration(force=True)

    assert len(recorded) == 1
    req = recorded[0]
    assert req.headers.get("Authorization") == "Bearer token-secret"
    assert "api_key" not in str(req.url)
    assert "token-secret" not in str(req.url)


@pytest.mark.asyncio
async def test_api_key_fallback_without_bearer() -> None:
    recorded: list[httpx.Request] = []
    transport = httpx.MockTransport(_handler_factory(recorded, default_json=CONFIGURATION))
    settings = _settings(tmdb_api_key=SecretStr("only-key"))
    async with httpx.AsyncClient(transport=transport) as http:
        client = TmdbClient(settings, http)
        assert client.auth_mode == "api_key"
        await client.get_configuration(force=True)

    req = recorded[0]
    assert "Authorization" not in req.headers
    assert req.url.params.get("api_key") == "only-key"


@pytest.mark.asyncio
async def test_not_configured_raises() -> None:
    settings = _settings()
    async with httpx.AsyncClient() as http:
        client = TmdbClient(settings, http)
        assert client.auth_mode == "none"
        with pytest.raises(TmdbNotConfiguredError):
            await client.get_json("/configuration")


@pytest.mark.asyncio
async def test_search_movie_sends_include_adult_language_region() -> None:
    recorded: list[httpx.Request] = []
    transport = httpx.MockTransport(
        _handler_factory(recorded, default_json={"results": [], "page": 1})
    )
    settings = _settings(tmdb_api_read_access_token=SecretStr("tok"))
    async with httpx.AsyncClient(transport=transport) as http:
        client = TmdbClient(settings, http)
        await client.search_movie(query="오펜하이머", page=2)

    req = recorded[0]
    assert req.url.path.endswith("/search/movie")
    params = req.url.params
    assert params.get("include_adult") == "true"
    assert INCLUDE_ADULT is True
    assert params.get("language") == "ko-KR"
    assert params.get("region") == "KR"
    assert params.get("query") == "오펜하이머"
    assert params.get("page") == "2"


@pytest.mark.asyncio
async def test_search_tv_include_adult_no_region() -> None:
    recorded: list[httpx.Request] = []
    transport = httpx.MockTransport(
        _handler_factory(recorded, default_json={"results": [], "page": 1})
    )
    settings = _settings(tmdb_api_read_access_token=SecretStr("tok"))
    async with httpx.AsyncClient(transport=transport) as http:
        client = TmdbClient(settings, http)
        await client.search_tv(query="오징어 게임", page=1)

    params = recorded[0].url.params
    assert recorded[0].url.path.endswith("/search/tv")
    assert params.get("include_adult") == "true"
    assert params.get("language") == "ko-KR"
    assert "region" not in params


@pytest.mark.asyncio
async def test_search_multi_include_adult_no_region() -> None:
    recorded: list[httpx.Request] = []
    transport = httpx.MockTransport(
        _handler_factory(recorded, default_json={"results": [], "page": 1})
    )
    settings = _settings(tmdb_api_read_access_token=SecretStr("tok"))
    async with httpx.AsyncClient(transport=transport) as http:
        client = TmdbClient(settings, http)
        await client.search_multi(query="배트맨", page=1)

    params = recorded[0].url.params
    assert recorded[0].url.path.endswith("/search/multi")
    assert params.get("include_adult") == "true"
    assert "region" not in params


@pytest.mark.asyncio
async def test_details_append_to_response() -> None:
    recorded: list[httpx.Request] = []
    transport = httpx.MockTransport(_handler_factory(recorded, default_json={"id": 1}))
    settings = _settings(tmdb_api_read_access_token=SecretStr("tok"))
    async with httpx.AsyncClient(transport=transport) as http:
        client = TmdbClient(settings, http)
        await client.movie_details(872585)
        await client.tv_details(93405)

    assert recorded[0].url.path.endswith("/movie/872585")
    assert recorded[0].url.params.get("append_to_response") == "credits,external_ids"
    assert recorded[1].url.path.endswith("/tv/93405")
    assert recorded[1].url.params.get("append_to_response") == "credits,external_ids"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "exc_type"),
    [
        (401, TmdbAuthFailedError),
        (403, TmdbAuthFailedError),
        (404, TmdbNotFoundError),
        (429, TmdbRateLimitedError),
        (500, TmdbUpstreamError),
    ],
)
async def test_http_error_mapping(status: int, exc_type: type[Exception]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        headers = {"Retry-After": "3"} if status == 429 else {}
        return httpx.Response(status, headers=headers, json={"status_message": "x"})

    settings = _settings(tmdb_api_read_access_token=SecretStr("tok"))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = TmdbClient(settings, http)
        with pytest.raises(exc_type) as raised:
            await client.get_json("/movie/1", allow_retry=False)
    if status == 429:
        assert raised.value.retry_after == "3"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_invalid_json_is_upstream_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json", headers={"content-type": "text/plain"})

    settings = _settings(tmdb_api_read_access_token=SecretStr("tok"))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = TmdbClient(settings, http)
        with pytest.raises(TmdbUpstreamError):
            await client.get_json("/configuration")


@pytest.mark.asyncio
async def test_status_not_configured_without_network() -> None:
    settings = _settings()
    async with httpx.AsyncClient() as http:
        client = TmdbClient(settings, http)
        payload = await client.probe_status(force=True)
    assert payload["status"] == "NOT_CONFIGURED"
    assert payload["configured"] is False
    assert payload["auth_mode"] == "none"


@pytest.mark.asyncio
async def test_status_available() -> None:
    transport = httpx.MockTransport(
        lambda r: httpx.Response(200, json=CONFIGURATION)
    )
    settings = _settings(tmdb_api_read_access_token=SecretStr("tok"))
    async with httpx.AsyncClient(transport=transport) as http:
        client = TmdbClient(settings, http)
        payload = await client.probe_status(force=True)
    assert payload["status"] == "AVAILABLE"
    assert payload["available"] is True
    assert payload["auth_mode"] == "bearer"
    assert "tok" not in json.dumps(payload)


@pytest.mark.asyncio
async def test_timeout_maps_to_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout", request=request)

    settings = _settings(tmdb_api_read_access_token=SecretStr("tok"))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = TmdbClient(settings, http)
        with pytest.raises(TmdbUnavailableError):
            await client.get_json("/configuration", allow_retry=False)
