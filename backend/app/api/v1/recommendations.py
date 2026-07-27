"""Random recommendation API (REC-1)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.recommendation import (
    RandomRecommendationRequest,
    RandomRecommendationResponse,
)
from app.services import recommendation_service

router = APIRouter(tags=["recommendations"])


@router.post(
    "/recommendations/random",
    response_model=RandomRecommendationResponse,
)
def post_random_recommendation(
    payload: RandomRecommendationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RandomRecommendationResponse:
    result = recommendation_service.get_random_recommendation(
        db,
        user,
        category_id=payload.category_id,
        status_filter=payload.status_filter,
    )
    return RandomRecommendationResponse(**result)
