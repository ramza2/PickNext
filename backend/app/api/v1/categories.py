from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas import CategoryListResponse, CategoryResponse
from app.services import catalog

router = APIRouter(tags=["categories"])


@router.get("/categories", response_model=CategoryListResponse)
def read_categories(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CategoryListResponse:
    rows = catalog.list_categories_with_counts(db, user)
    return CategoryListResponse(categories=[CategoryResponse(**row) for row in rows])
