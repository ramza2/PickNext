from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import CategoryType, ItemStatus, StatusFilter


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str
    database: str


class UserCreate(BaseModel):
    email: str
    display_name: str = Field(min_length=1, max_length=100)
    password_hash: str = Field(min_length=1, max_length=255)


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category_type: CategoryType
    sort_order: int = 0


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ItemCreate(BaseModel):
    category_id: UUID
    title: str = Field(min_length=1, max_length=300)
    status: ItemStatus
    rating: Decimal = Field(ge=Decimal("0"), le=Decimal("5"))
    collection_id: UUID | None = None
    progress_note: str | None = Field(default=None, max_length=200)
    memo: str | None = None

    @field_validator("rating")
    @classmethod
    def rating_half_step(cls, value: Decimal) -> Decimal:
        rating = Decimal(str(value))
        if (rating * 2) != (rating * 2).to_integral_value():
            raise ValueError("rating must be in 0.5 increments")
        return rating


class RecommendationHistoryCreate(BaseModel):
    category_id: UUID
    status_filter: StatusFilter
    collection_id: UUID | None = None
    selected_at: datetime | None = None


class RecommendationHistoryItemCreate(BaseModel):
    item_id: UUID
    title_snapshot: str = Field(min_length=1, max_length=300)
    status_at_selection: ItemStatus
    sort_order: int = 0
