from fastapi import APIRouter

from app.api.v1 import categories, collections, health, items, summary

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(summary.router)
api_router.include_router(categories.router)
api_router.include_router(collections.router)
api_router.include_router(items.router)
