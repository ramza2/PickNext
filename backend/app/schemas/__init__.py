from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.models import CategoryType, ItemStatus, StatusFilter
from app.services.catalog import ItemSort, SortOrder


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
    title: str = Field(min_length=1)
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


class SummaryResponse(BaseModel):
    item_count: int
    planned_count: int
    completed_count: int
    collection_count: int
    category_count: int


class CategoryResponse(BaseModel):
    id: UUID
    name: str
    category_type: CategoryType
    sort_order: int
    item_count: int
    planned_count: int
    completed_count: int


class CategoryListResponse(BaseModel):
    categories: list[CategoryResponse]


class CategoryRef(BaseModel):
    id: UUID
    name: str


class CollectionRef(BaseModel):
    id: UUID
    name: str


class ItemListItem(BaseModel):
    id: UUID
    title: str
    status: ItemStatus
    rating: Decimal
    progress_note: str | None
    category: CategoryRef
    collection: CollectionRef | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("rating")
    def serialize_rating(self, value: Decimal) -> float:
        return float(value)


class ItemListResponse(BaseModel):
    items: list[ItemListItem]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_previous: bool


class ItemDetailResponse(ItemListItem):
    memo: str | None


__all__ = [
    "CategoryCreate",
    "CategoryListResponse",
    "CategoryRef",
    "CategoryResponse",
    "CollectionCreate",
    "CollectionRef",
    "HealthResponse",
    "ItemCreate",
    "ItemDetailResponse",
    "ItemListItem",
    "ItemListResponse",
    "ItemSort",
    "ORMModel",
    "RecommendationHistoryCreate",
    "RecommendationHistoryItemCreate",
    "SortOrder",
    "SummaryResponse",
    "UserCreate",
]
