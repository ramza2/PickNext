from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.integrations.tmdb.client import TmdbClient
from app.services.tmdb_service import TmdbService

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class OriginAllowlistMiddleware(BaseHTTPMiddleware):
    """Reject unsafe browser requests whose Origin is outside CORS allowlist."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        if request.method in _UNSAFE_METHODS:
            origin = request.headers.get("origin")
            if origin:
                settings = get_settings()
                if origin not in settings.cors_origins:
                    return Response(
                        content='{"detail":{"code":"AUTH_ORIGIN_DENIED","message":"Origin not allowed"}}',
                        status_code=403,
                        media_type="application/json",
                    )
        return await call_next(request)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.tmdb_request_timeout_seconds),
    )
    tmdb_client = TmdbClient(settings, http_client)
    application.state.http_client = http_client
    application.state.tmdb_client = tmdb_client
    application.state.tmdb_service = TmdbService(settings, tmdb_client)
    try:
        yield
    finally:
        await http_client.aclose()


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    if "*" in settings.cors_origins:
        raise RuntimeError("cors_origins must not include '*' when credentials are enabled")

    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )
    application.add_middleware(OriginAllowlistMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix=settings.api_v1_prefix)
    return application


app = create_app()
