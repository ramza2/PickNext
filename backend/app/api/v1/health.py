from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={
        503: {
            "model": HealthResponse,
            "description": "Database unavailable",
        }
    },
)
def health_check(db: Session = Depends(get_db)) -> HealthResponse | JSONResponse:
    try:
        db.execute(text("SELECT 1"))
        return HealthResponse(status="ok", database="connected")
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "database": "disconnected"},
        )
