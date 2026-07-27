"""Random recommendation: Collection-aware candidates, no history write."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Category,
    Collection,
    Item,
    ItemStatus,
    StatusFilter,
    User,
)
from app.services.catalog import _item_list_dict

CandidateType = Literal["ITEM", "COLLECTION"]


@dataclass(frozen=True, slots=True)
class RecommendationCandidate:
    candidate_type: CandidateType
    candidate_id: UUID


class RandomIndexProvider(Protocol):
    def next_index(self, upper_bound: int) -> int:
        """Return an integer in ``[0, upper_bound)``."""


class SecureRandomIndexProvider:
    def next_index(self, upper_bound: int) -> int:
        if upper_bound <= 0:
            raise ValueError("upper_bound must be positive")
        return secrets.randbelow(upper_bound)


def _get_owned_category(db: Session, user: User, category_id: UUID) -> Category:
    category = db.scalar(
        select(Category).where(
            Category.id == category_id,
            Category.user_id == user.id,
        )
    )
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    return category


def _status_match(status_filter: StatusFilter) -> ItemStatus | None:
    if status_filter == StatusFilter.ALL:
        return None
    if status_filter == StatusFilter.PLANNED:
        return ItemStatus.PLANNED
    return ItemStatus.COMPLETED


def _base_item_conditions(
    user: User,
    category_id: UUID,
    status_filter: StatusFilter,
) -> list:
    conditions = [
        Item.user_id == user.id,
        Item.category_id == category_id,
    ]
    item_status = _status_match(status_filter)
    if item_status is not None:
        conditions.append(Item.status == item_status)
    return conditions


def _item_candidate_stmt(
    user: User,
    category_id: UUID,
    status_filter: StatusFilter,
) -> Select[tuple[UUID]]:
    conditions = _base_item_conditions(user, category_id, status_filter)
    conditions.append(Item.collection_id.is_(None))
    return select(Item.id).where(and_(*conditions)).order_by(Item.id.asc())


def _collection_candidate_stmt(
    user: User,
    category_id: UUID,
    status_filter: StatusFilter,
) -> Select[tuple[UUID]]:
    conditions = _base_item_conditions(user, category_id, status_filter)
    conditions.append(Item.collection_id.is_not(None))
    return (
        select(Item.collection_id)
        .where(and_(*conditions))
        .distinct()
        .order_by(Item.collection_id.asc())
    )


def list_eligible_candidates(
    db: Session,
    user: User,
    category_id: UUID,
    status_filter: StatusFilter,
) -> list[RecommendationCandidate]:
    """Build candidate pool: standalone Items + distinct Collections (equal weight).

    Recommendation history does not affect eligibility.
    """
    item_ids = db.scalars(
        _item_candidate_stmt(user, category_id, status_filter)
    ).all()
    collection_ids = db.scalars(
        _collection_candidate_stmt(user, category_id, status_filter)
    ).all()

    candidates = [
        RecommendationCandidate("ITEM", item_id) for item_id in item_ids
    ]
    candidates.extend(
        RecommendationCandidate("COLLECTION", collection_id)
        for collection_id in collection_ids
        if collection_id is not None
    )
    return candidates


def load_collection_items(db: Session, user: User, collection_id: UUID) -> list[Item]:
    """All items in a collection for the user, stable sort."""
    return list(
        db.scalars(
            select(Item)
            .options(
                joinedload(Item.category),
                joinedload(Item.collection),
            )
            .join(Category, Item.category_id == Category.id)
            .where(
                Item.user_id == user.id,
                Item.collection_id == collection_id,
            )
            .order_by(
                Category.sort_order.asc(),
                Item.created_at.asc(),
                Item.id.asc(),
            )
        ).unique().all()
    )


def load_standalone_item(db: Session, user: User, item_id: UUID) -> Item | None:
    return db.scalar(
        select(Item)
        .options(
            joinedload(Item.category),
            joinedload(Item.collection),
        )
        .where(
            Item.id == item_id,
            Item.user_id == user.id,
            Item.collection_id.is_(None),
        )
    )


def _empty_response(category: Category, status_filter: StatusFilter) -> dict:
    return {
        "category": {"id": category.id, "name": category.name},
        "status_filter": status_filter,
        "candidate_type": None,
        "candidate_id": None,
        "collection": None,
        "items": [],
        "eligible_candidate_count": 0,
    }


def _result_for_candidate(
    db: Session,
    user: User,
    category: Category,
    status_filter: StatusFilter,
    candidate: RecommendationCandidate,
    eligible_count: int,
) -> dict:
    if candidate.candidate_type == "ITEM":
        item = load_standalone_item(db, user, candidate.candidate_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found",
            )
        return {
            "category": {"id": category.id, "name": category.name},
            "status_filter": status_filter,
            "candidate_type": "ITEM",
            "candidate_id": item.id,
            "collection": None,
            "items": [_item_list_dict(item)],
            "eligible_candidate_count": eligible_count,
        }

    collection = db.scalar(
        select(Collection).where(
            Collection.id == candidate.candidate_id,
            Collection.user_id == user.id,
        )
    )
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        )
    items = load_collection_items(db, user, collection.id)
    return {
        "category": {"id": category.id, "name": category.name},
        "status_filter": status_filter,
        "candidate_type": "COLLECTION",
        "candidate_id": collection.id,
        "collection": {"id": collection.id, "name": collection.name},
        "items": [_item_list_dict(item) for item in items],
        "eligible_candidate_count": eligible_count,
    }


def get_random_recommendation(
    db: Session,
    user: User,
    *,
    category_id: UUID,
    status_filter: StatusFilter,
    random_provider: RandomIndexProvider | None = None,
) -> dict:
    category = _get_owned_category(db, user, category_id)
    candidates = list_eligible_candidates(db, user, category_id, status_filter)
    if not candidates:
        return _empty_response(category, status_filter)

    provider = random_provider or SecureRandomIndexProvider()
    index = provider.next_index(len(candidates))
    selected = candidates[index]
    return _result_for_candidate(
        db,
        user,
        category,
        status_filter,
        selected,
        eligible_count=len(candidates),
    )


def count_matching_items_in_collection(
    db: Session,
    user: User,
    *,
    collection_id: UUID,
    category_id: UUID,
    status_filter: StatusFilter,
) -> int:
    conditions = _base_item_conditions(user, category_id, status_filter)
    conditions.append(Item.collection_id == collection_id)
    return int(db.scalar(select(func.count()).select_from(Item).where(and_(*conditions))) or 0)
