from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas import SummaryResponse
from app.services import catalog

router = APIRouter(tags=["summary"])


@router.get("/summary", response_model=SummaryResponse)
def read_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SummaryResponse:
    return SummaryResponse(**catalog.get_summary(db, user))
