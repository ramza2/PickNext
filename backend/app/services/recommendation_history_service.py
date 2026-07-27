"""Recommendation history: explicit save, list, detail, delete."""

from __future__ import annotations

import math
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Collection,
    Item,
    RecommendationHistory,
    RecommendationHistoryItem,
    StatusFilter,
    User,
)
from app.services.catalog import _item_list_dict
from app.services.recommendation_service import (
    _get_owned_category,
    _status_match,
    count_matching_items_in_collection,
    load_collection_items,
    load_standalone_item,
)
from app.integrations.tmdb.images import item_poster_url


def create_recommendation_history(
    db: Session,
    user: User,
    *,
    category_id: UUID,
    status_filter: StatusFilter,
    candidate_type: str,
    candidate_id: UUID,
    commit: bool = True,
) -> RecommendationHistory:
    category = _get_owned_category(db, user, category_id)

    if candidate_type == "ITEM":
        item = load_standalone_item(db, user, candidate_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found",
            )
        if item.category_id != category.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found",
            )
        required_status = _status_match(status_filter)
        if required_status is not None and item.status != required_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found",
            )

        history = RecommendationHistory(
            user_id=user.id,
            category_id=category.id,
            status_filter=status_filter,
            collection_id=None,
        )
        db.add(history)
        db.flush()
        db.add(
            RecommendationHistoryItem(
                recommendation_history_id=history.id,
                item_id=item.id,
                title_snapshot=item.title,
                status_at_selection=item.status,
                sort_order=0,
            )
        )
    elif candidate_type == "COLLECTION":
        collection = db.scalar(
            select(Collection).where(
                Collection.id == candidate_id,
                Collection.user_id == user.id,
            )
        )
        if collection is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collection not found",
            )
        match_count = count_matching_items_in_collection(
            db,
            user,
            collection_id=collection.id,
            category_id=category.id,
            status_filter=status_filter,
        )
        if match_count < 1:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collection not found",
            )

        items = load_collection_items(db, user, collection.id)
        if not items:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collection not found",
            )

        history = RecommendationHistory(
            user_id=user.id,
            category_id=category.id,
            status_filter=status_filter,
            collection_id=collection.id,
        )
        db.add(history)
        db.flush()
        for sort_order, item in enumerate(items):
            db.add(
                RecommendationHistoryItem(
                    recommendation_history_id=history.id,
                    item_id=item.id,
                    title_snapshot=item.title,
                    status_at_selection=item.status,
                    sort_order=sort_order,
                )
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid candidate_type",
        )

    try:
        db.flush()
        if commit:
            db.commit()
            db.refresh(history)
        return history
    except Exception:
        if commit:
            db.rollback()
        raise


def _history_with_relations(db: Session, user: User, history_id: UUID) -> RecommendationHistory:
    history = db.scalar(
        select(RecommendationHistory)
        .options(
            joinedload(RecommendationHistory.category),
            joinedload(RecommendationHistory.collection),
            joinedload(RecommendationHistory.items).joinedload(
                RecommendationHistoryItem.item
            ).joinedload(Item.category),
            joinedload(RecommendationHistory.items).joinedload(
                RecommendationHistoryItem.item
            ).joinedload(Item.collection),
        )
        .where(
            RecommendationHistory.id == history_id,
            RecommendationHistory.user_id == user.id,
        )
    )
    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation history not found",
        )
    return history


def _sorted_history_items(
    history: RecommendationHistory,
) -> list[RecommendationHistoryItem]:
    return sorted(history.items, key=lambda row: (row.sort_order, str(row.id)))


def _list_item_payload(history: RecommendationHistory) -> dict:
    rows = _sorted_history_items(history)
    first = rows[0] if rows else None
    item = first.item if first is not None else None
    title = (
        history.collection.name
        if history.collection is not None
        else (first.title_snapshot if first is not None else "")
    )
    candidate_type = "COLLECTION" if history.collection_id is not None else "ITEM"
    return {
        "id": history.id,
        "category": {"id": history.category.id, "name": history.category.name},
        "status_filter": history.status_filter,
        "collection": (
            {"id": history.collection.id, "name": history.collection.name}
            if history.collection is not None
            else None
        ),
        "selected_at": history.selected_at,
        "title": title,
        "item_count": len(rows),
        "poster_url": (
            item_poster_url(
                external_source=item.external_source,
                poster_path=item.poster_path,
            )
            if item is not None
            else None
        ),
        "release_year": item.release_year if item is not None else None,
        "candidate_type": candidate_type,
    }


def list_recommendation_history(
    db: Session,
    user: User,
    *,
    page: int = 1,
    page_size: int = 25,
) -> dict:
    count_stmt = (
        select(func.count())
        .select_from(RecommendationHistory)
        .where(RecommendationHistory.user_id == user.id)
    )
    total = int(db.scalar(count_stmt) or 0)
    total_pages = math.ceil(total / page_size) if total else 0
    offset = (page - 1) * page_size

    histories = db.scalars(
        select(RecommendationHistory)
        .options(
            joinedload(RecommendationHistory.category),
            joinedload(RecommendationHistory.collection),
            joinedload(RecommendationHistory.items).joinedload(
                RecommendationHistoryItem.item
            ),
        )
        .where(RecommendationHistory.user_id == user.id)
        .order_by(
            RecommendationHistory.selected_at.desc(),
            RecommendationHistory.id.desc(),
        )
        .offset(offset)
        .limit(page_size)
    ).unique().all()

    return {
        "items": [_list_item_payload(history) for history in histories],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1 and total > 0,
    }


def get_recommendation_history_detail(
    db: Session,
    user: User,
    history_id: UUID,
) -> dict:
    history = _history_with_relations(db, user, history_id)
    rows = _sorted_history_items(history)
    detail_items = []
    for row in rows:
        current = None
        item_exists = row.item is not None
        if item_exists:
            current = _item_list_dict(row.item)
        detail_items.append(
            {
                "item_id": row.item_id,
                "title_snapshot": row.title_snapshot,
                "status_at_selection": row.status_at_selection,
                "sort_order": row.sort_order,
                "item_exists": item_exists,
                "current": current,
            }
        )

    return {
        "id": history.id,
        "category": {"id": history.category.id, "name": history.category.name},
        "status_filter": history.status_filter,
        "collection": (
            {"id": history.collection.id, "name": history.collection.name}
            if history.collection is not None
            else None
        ),
        "selected_at": history.selected_at,
        "candidate_type": (
            "COLLECTION" if history.collection_id is not None else "ITEM"
        ),
        "items": detail_items,
    }


def delete_recommendation_history(
    db: Session,
    user: User,
    history_id: UUID,
    *,
    commit: bool = True,
) -> None:
    history = db.scalar(
        select(RecommendationHistory).where(
            RecommendationHistory.id == history_id,
            RecommendationHistory.user_id == user.id,
        )
    )
    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation history not found",
        )
    try:
        db.delete(history)
        db.flush()
        if commit:
            db.commit()
    except Exception:
        if commit:
            db.rollback()
        raise


def delete_all_recommendation_history(
    db: Session,
    user: User,
    *,
    commit: bool = True,
) -> int:
    count = int(
        db.scalar(
            select(func.count())
            .select_from(RecommendationHistory)
            .where(RecommendationHistory.user_id == user.id)
        )
        or 0
    )
    try:
        db.execute(
            delete(RecommendationHistory).where(
                RecommendationHistory.user_id == user.id,
            )
        )
        db.flush()
        if commit:
            db.commit()
        return count
    except Exception:
        if commit:
            db.rollback()
        raise
