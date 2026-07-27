"""Schemas for random recommendation and recommendation history (REC-1)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models import ItemStatus, StatusFilter
from app.schemas import CategoryRef, CollectionRef, ItemListItem

RecommendationCandidateType = Literal["ITEM", "COLLECTION"]


class RandomRecommendationRequest(BaseModel):
    category_id: UUID
    status_filter: StatusFilter


class RandomRecommendationResponse(BaseModel):
    category: CategoryRef
    status_filter: StatusFilter
    candidate_type: RecommendationCandidateType | None
    candidate_id: UUID | None = None
    collection: CollectionRef | None = None
    items: list[ItemListItem]
    eligible_candidate_count: int


class CreateRecommendationHistoryRequest(BaseModel):
    category_id: UUID
    status_filter: StatusFilter
    candidate_type: RecommendationCandidateType
    candidate_id: UUID


class RecommendationHistoryListItem(BaseModel):
    id: UUID
    category: CategoryRef
    status_filter: StatusFilter
    collection: CollectionRef | None
    selected_at: datetime
    title: str
    item_count: int
    poster_url: str | None = None
    release_year: int | None = None
    candidate_type: RecommendationCandidateType


class RecommendationHistoryListResponse(BaseModel):
    items: list[RecommendationHistoryListItem]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_previous: bool


class RecommendationHistoryDetailItem(BaseModel):
    item_id: UUID
    title_snapshot: str
    status_at_selection: ItemStatus
    sort_order: int
    item_exists: bool = True
    current: ItemListItem | None = None


class RecommendationHistoryDetailResponse(BaseModel):
    id: UUID
    category: CategoryRef
    status_filter: StatusFilter
    collection: CollectionRef | None
    selected_at: datetime
    candidate_type: RecommendationCandidateType
    items: list[RecommendationHistoryDetailItem]


class RecommendationHistoryDeleteAllResponse(BaseModel):
    deleted_count: int = Field(ge=0)
