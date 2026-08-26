from fastapi import APIRouter

from app.api.v1 import (
    auth,
    categories,
    collections,
    health,
    items,
    recommendation_history,
    recommendations,
    settings_database,
    summary,
    tmdb,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router)
api_router.include_router(summary.router)
api_router.include_router(categories.router)
api_router.include_router(collections.router)
api_router.include_router(items.router)
api_router.include_router(recommendations.router)
api_router.include_router(recommendation_history.router)
api_router.include_router(tmdb.router)
api_router.include_router(settings_database.router)
