"""Recommendation history API (REC-1)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.recommendation import (
    CreateRecommendationHistoryRequest,
    RecommendationHistoryDeleteAllResponse,
    RecommendationHistoryDetailResponse,
    RecommendationHistoryListResponse,
)
from app.services import recommendation_history_service

router = APIRouter(tags=["recommendation-history"])


@router.get(
    "/recommendation-history",
    response_model=RecommendationHistoryListResponse,
)
def list_recommendation_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RecommendationHistoryListResponse:
    payload = recommendation_history_service.list_recommendation_history(
        db,
        user,
        page=page,
        page_size=page_size,
    )
    return RecommendationHistoryListResponse(**payload)


@router.get(
    "/recommendation-history/{history_id}",
    response_model=RecommendationHistoryDetailResponse,
)
def get_recommendation_history(
    history_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RecommendationHistoryDetailResponse:
    payload = recommendation_history_service.get_recommendation_history_detail(
        db,
        user,
        history_id,
    )
    return RecommendationHistoryDetailResponse(**payload)


@router.post(
    "/recommendation-history",
    response_model=RecommendationHistoryDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_recommendation_history(
    payload: CreateRecommendationHistoryRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RecommendationHistoryDetailResponse:
    history = recommendation_history_service.create_recommendation_history(
        db,
        user,
        category_id=payload.category_id,
        status_filter=payload.status_filter,
        candidate_type=payload.candidate_type,
        candidate_id=payload.candidate_id,
    )
    detail = recommendation_history_service.get_recommendation_history_detail(
        db,
        user,
        history.id,
    )
    return RecommendationHistoryDetailResponse(**detail)


@router.delete(
    "/recommendation-history/{history_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_recommendation_history(
    history_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    recommendation_history_service.delete_recommendation_history(
        db,
        user,
        history_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/recommendation-history",
    response_model=RecommendationHistoryDeleteAllResponse,
)
def delete_all_recommendation_history(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RecommendationHistoryDeleteAllResponse:
    deleted_count = recommendation_history_service.delete_all_recommendation_history(
        db,
        user,
    )
    return RecommendationHistoryDeleteAllResponse(deleted_count=deleted_count)
