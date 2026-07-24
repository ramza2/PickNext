from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.models import CategoryType, ItemStatus, StatusFilter
from app.services.catalog import CollectionSort, ItemSort, SortOrder


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


def _normalize_collection_name(value: object) -> str:
    if value is None:
        raise ValueError("name must not be empty")
    if not isinstance(value, str):
        raise TypeError("name must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError("name must not be empty")
    if len(normalized) > 200:
        raise ValueError("name must be at most 200 characters")
    return normalized


def _normalize_item_title(value: object) -> str:
    if value is None:
        raise ValueError("title must not be empty")
    if not isinstance(value, str):
        raise TypeError("title must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError("title must not be empty")
    return normalized


def _normalize_item_rating(value: object) -> Decimal:
    if isinstance(value, bool):
        raise TypeError("rating must be a number")
    try:
        rating = Decimal(str(value))
    except Exception as exc:
        raise ValueError("rating must be a number") from exc
    if not rating.is_finite():
        raise ValueError("rating must be a finite number")
    if rating < Decimal("0") or rating > Decimal("5"):
        raise ValueError("rating must be between 0.0 and 5.0")
    if (rating * 2) != (rating * 2).to_integral_value():
        raise ValueError("rating must be in 0.5 increments")
    return rating


def _normalize_optional_progress_note(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("progress_note must be a string")
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > 200:
        raise ValueError("progress_note must be at most 200 characters")
    return normalized


def _normalize_optional_memo(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("memo must be a string")
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


class CollectionCreate(BaseModel):
    name: str

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> str:
        return _normalize_collection_name(value)


class CollectionUpdate(BaseModel):
    name: str

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> str:
        return _normalize_collection_name(value)


class ItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    category_id: UUID
    collection_id: UUID | None = None
    status: ItemStatus = ItemStatus.PLANNED
    rating: Decimal = Decimal("0.0")
    progress_note: str | None = None
    memo: str | None = None

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: object) -> str:
        return _normalize_item_title(value)

    @field_validator("rating", mode="before")
    @classmethod
    def normalize_rating(cls, value: object) -> Decimal:
        if value is None:
            raise ValueError("rating must not be null")
        return _normalize_item_rating(value)

    @field_validator("progress_note", mode="before")
    @classmethod
    def normalize_progress_note(cls, value: object) -> str | None:
        return _normalize_optional_progress_note(value)

    @field_validator("memo", mode="before")
    @classmethod
    def normalize_memo(cls, value: object) -> str | None:
        return _normalize_optional_memo(value)


class ItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    category_id: UUID | None = None
    collection_id: UUID | None = None
    status: ItemStatus | None = None
    rating: Decimal | None = None
    progress_note: str | None = None
    memo: str | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_empty_body(cls, data: object) -> object:
        if isinstance(data, dict) and not data:
            raise ValueError("at least one field must be provided")
        return data

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: object) -> object:
        if value is None:
            return None
        return _normalize_item_title(value)

    @field_validator("rating", mode="before")
    @classmethod
    def normalize_rating(cls, value: object) -> object:
        if value is None:
            return None
        return _normalize_item_rating(value)

    @field_validator("progress_note", mode="before")
    @classmethod
    def normalize_progress_note(cls, value: object) -> object:
        if value is None:
            return None
        return _normalize_optional_progress_note(value)

    @field_validator("memo", mode="before")
    @classmethod
    def normalize_memo(cls, value: object) -> object:
        if value is None:
            return None
        return _normalize_optional_memo(value)

    @model_validator(mode="after")
    def validate_explicit_nulls(self) -> "ItemUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("title must not be null")
        if "category_id" in self.model_fields_set and self.category_id is None:
            raise ValueError("category_id must not be null")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status must not be null")
        if "rating" in self.model_fields_set and self.rating is None:
            raise ValueError("rating must not be null")
        return self


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


class CollectionCategoryCount(BaseModel):
    id: UUID
    name: str
    item_count: int


class CollectionResponse(BaseModel):
    id: UUID
    name: str
    item_count: int
    planned_count: int
    completed_count: int
    categories: list[CollectionCategoryCount]
    created_at: datetime
    updated_at: datetime


class CollectionListResponse(BaseModel):
    collections: list[CollectionResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_previous: bool


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
    external_source: str | None = None
    external_id: str | None = None
    external_media_type: str | None = None
    original_title: str | None = None
    original_language: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None

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
    "CollectionCategoryCount",
    "CollectionCreate",
    "CollectionListResponse",
    "CollectionRef",
    "CollectionResponse",
    "CollectionSort",
    "CollectionUpdate",
    "HealthResponse",
    "ItemCreate",
    "ItemDetailResponse",
    "ItemListItem",
    "ItemListResponse",
    "ItemSort",
    "ItemUpdate",
    "ORMModel",
    "RecommendationHistoryCreate",
    "RecommendationHistoryItemCreate",
    "SortOrder",
    "SummaryResponse",
    "UserCreate",
]
