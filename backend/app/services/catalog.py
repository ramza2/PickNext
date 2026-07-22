"""Read-only catalog queries: summary, categories, items, collections."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Select, asc, desc, exists, func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Category, Collection, Item, ItemStatus, User


class ItemSort(str, Enum):
    UPDATED_AT = "updated_at"
    CREATED_AT = "created_at"
    TITLE = "title"
    RATING = "rating"
    STATUS = "status"


class CollectionSort(str, Enum):
    UPDATED_AT = "updated_at"
    CREATED_AT = "created_at"
    NAME = "name"
    ITEM_COUNT = "item_count"
    COMPLETED_COUNT = "completed_count"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


def escape_like_pattern(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@dataclass(frozen=True)
class ItemListParams:
    page: int = 1
    page_size: int = 25
    search: str | None = None
    category_id: UUID | None = None
    status: ItemStatus | None = None
    collection_id: UUID | None = None
    has_collection: bool | None = None
    sort: ItemSort = ItemSort.UPDATED_AT
    order: SortOrder = SortOrder.DESC


@dataclass(frozen=True)
class CollectionListParams:
    page: int = 1
    page_size: int = 25
    search: str | None = None
    category_id: UUID | None = None
    status: ItemStatus | None = None
    sort: CollectionSort = CollectionSort.UPDATED_AT
    order: SortOrder = SortOrder.DESC


def get_summary(db: Session, user: User) -> dict[str, int]:
    item_stats = db.execute(
        select(
            func.count().label("item_count"),
            func.count().filter(Item.status == ItemStatus.PLANNED).label("planned_count"),
            func.count().filter(Item.status == ItemStatus.COMPLETED).label("completed_count"),
        ).where(Item.user_id == user.id)
    ).one()
    collection_count = db.scalar(
        select(func.count()).select_from(Collection).where(Collection.user_id == user.id)
    )
    category_count = db.scalar(
        select(func.count()).select_from(Category).where(Category.user_id == user.id)
    )
    return {
        "item_count": int(item_stats.item_count or 0),
        "planned_count": int(item_stats.planned_count or 0),
        "completed_count": int(item_stats.completed_count or 0),
        "collection_count": int(collection_count or 0),
        "category_count": int(category_count or 0),
    }


def list_categories_with_counts(db: Session, user: User) -> list[dict[str, Any]]:
    counts_subq = (
        select(
            Item.category_id.label("category_id"),
            func.count().label("item_count"),
            func.count().filter(Item.status == ItemStatus.PLANNED).label("planned_count"),
            func.count().filter(Item.status == ItemStatus.COMPLETED).label("completed_count"),
        )
        .where(Item.user_id == user.id)
        .group_by(Item.category_id)
        .subquery()
    )
    rows = db.execute(
        select(
            Category,
            func.coalesce(counts_subq.c.item_count, 0),
            func.coalesce(counts_subq.c.planned_count, 0),
            func.coalesce(counts_subq.c.completed_count, 0),
        )
        .outerjoin(counts_subq, counts_subq.c.category_id == Category.id)
        .where(Category.user_id == user.id)
        .order_by(Category.sort_order.asc(), Category.name.asc())
    ).all()

    result: list[dict[str, Any]] = []
    for category, item_count, planned_count, completed_count in rows:
        result.append(
            {
                "id": category.id,
                "name": category.name,
                "category_type": category.category_type,
                "sort_order": category.sort_order,
                "item_count": int(item_count),
                "planned_count": int(planned_count),
                "completed_count": int(completed_count),
            }
        )
    return result


def _validate_collection_filters(params: ItemListParams) -> None:
    if params.has_collection is False and params.collection_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="collection_id cannot be set when has_collection is false",
        )


def _apply_item_filters(stmt: Select[Any], user: User, params: ItemListParams) -> Select[Any]:
    stmt = stmt.where(Item.user_id == user.id)

    if params.category_id is not None:
        stmt = stmt.where(Item.category_id == params.category_id)
    if params.status is not None:
        stmt = stmt.where(Item.status == params.status)
    if params.collection_id is not None:
        stmt = stmt.where(Item.collection_id == params.collection_id)
    if params.has_collection is True:
        stmt = stmt.where(Item.collection_id.is_not(None))
    elif params.has_collection is False:
        stmt = stmt.where(Item.collection_id.is_(None))

    if params.search is not None:
        trimmed = params.search.strip()
        if trimmed:
            pattern = f"%{escape_like_pattern(trimmed)}%"
            stmt = stmt.where(Item.title.ilike(pattern, escape="\\"))

    return stmt


def _apply_item_sort(stmt: Select[Any], params: ItemListParams) -> Select[Any]:
    direction = asc if params.order == SortOrder.ASC else desc
    sort_column = {
        ItemSort.UPDATED_AT: Item.updated_at,
        ItemSort.CREATED_AT: Item.created_at,
        ItemSort.TITLE: Item.title,
        ItemSort.RATING: Item.rating,
        ItemSort.STATUS: Item.status,
    }[params.sort]
    return stmt.order_by(direction(sort_column), direction(Item.id))


def list_items(db: Session, user: User, params: ItemListParams) -> dict[str, Any]:
    _validate_collection_filters(params)

    count_stmt = _apply_item_filters(select(func.count()).select_from(Item), user, params)
    total = int(db.scalar(count_stmt) or 0)
    total_pages = math.ceil(total / params.page_size) if total else 0
    offset = (params.page - 1) * params.page_size

    list_stmt = select(Item).options(
        joinedload(Item.category),
        joinedload(Item.collection),
    )
    list_stmt = _apply_item_filters(list_stmt, user, params)
    list_stmt = _apply_item_sort(list_stmt, params)
    list_stmt = list_stmt.offset(offset).limit(params.page_size)

    items = list(db.scalars(list_stmt).unique().all())

    return {
        "items": [_item_list_dict(item) for item in items],
        "page": params.page,
        "page_size": params.page_size,
        "total": total,
        "total_pages": total_pages,
        "has_next": params.page < total_pages,
        "has_previous": params.page > 1 and total > 0,
    }


def get_item_detail(db: Session, user: User, item_id: UUID) -> dict[str, Any]:
    item = db.scalar(
        select(Item)
        .options(
            joinedload(Item.category),
            joinedload(Item.collection),
        )
        .where(
            Item.id == item_id,
            Item.user_id == user.id,
        )
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    payload = _item_list_dict(item)
    payload["memo"] = item.memo
    return payload


def _category_ref(category: Category) -> dict[str, Any]:
    return {"id": category.id, "name": category.name}


def _collection_ref(collection: Collection | None) -> dict[str, Any] | None:
    if collection is None:
        return None
    return {"id": collection.id, "name": collection.name}


def _item_list_dict(item: Item) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "status": item.status,
        "rating": item.rating,
        "progress_note": item.progress_note,
        "category": _category_ref(item.category),
        "collection": _collection_ref(item.collection),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _collection_item_exists_clause(
    user_id: UUID,
    *,
    category_id: UUID | None = None,
    status: ItemStatus | None = None,
) -> Any:
    conditions = [
        Item.collection_id == Collection.id,
        Item.user_id == user_id,
    ]
    if category_id is not None:
        conditions.append(Item.category_id == category_id)
    if status is not None:
        conditions.append(Item.status == status)
    return exists(select(1).where(*conditions))


def _apply_collection_filters(
    stmt: Select[Any],
    user: User,
    params: CollectionListParams,
) -> Select[Any]:
    stmt = stmt.where(Collection.user_id == user.id)

    if params.search is not None:
        trimmed = params.search.strip()
        if trimmed:
            pattern = f"%{escape_like_pattern(trimmed)}%"
            stmt = stmt.where(Collection.name.ilike(pattern, escape="\\"))

    if params.category_id is not None or params.status is not None:
        stmt = stmt.where(
            _collection_item_exists_clause(
                user.id,
                category_id=params.category_id,
                status=params.status,
            )
        )

    return stmt


def _collection_status_agg_subquery(user_id: UUID) -> Any:
    return (
        select(
            Item.collection_id.label("collection_id"),
            func.count().label("item_count"),
            func.count().filter(Item.status == ItemStatus.PLANNED).label("planned_count"),
            func.count().filter(Item.status == ItemStatus.COMPLETED).label("completed_count"),
        )
        .where(
            Item.user_id == user_id,
            Item.collection_id.is_not(None),
        )
        .group_by(Item.collection_id)
        .subquery()
    )


def _apply_collection_sort(
    stmt: Select[Any],
    user: User,
    params: CollectionListParams,
) -> Select[Any]:
    direction = asc if params.order == SortOrder.ASC else desc

    if params.sort in (CollectionSort.ITEM_COUNT, CollectionSort.COMPLETED_COUNT):
        agg = _collection_status_agg_subquery(user.id)
        stmt = stmt.outerjoin(agg, agg.c.collection_id == Collection.id)
        sort_column = (
            func.coalesce(agg.c.item_count, 0)
            if params.sort == CollectionSort.ITEM_COUNT
            else func.coalesce(agg.c.completed_count, 0)
        )
        return stmt.order_by(direction(sort_column), direction(Collection.id))

    sort_column = {
        CollectionSort.UPDATED_AT: Collection.updated_at,
        CollectionSort.CREATED_AT: Collection.created_at,
        CollectionSort.NAME: Collection.name,
    }[params.sort]
    return stmt.order_by(direction(sort_column), direction(Collection.id))


def _status_counts_by_collection(
    db: Session,
    user: User,
    collection_ids: list[UUID],
) -> dict[UUID, tuple[int, int, int]]:
    if not collection_ids:
        return {}
    rows = db.execute(
        select(
            Item.collection_id,
            func.count().label("item_count"),
            func.count().filter(Item.status == ItemStatus.PLANNED).label("planned_count"),
            func.count().filter(Item.status == ItemStatus.COMPLETED).label("completed_count"),
        )
        .where(
            Item.user_id == user.id,
            Item.collection_id.in_(collection_ids),
        )
        .group_by(Item.collection_id)
    ).all()
    return {
        row.collection_id: (
            int(row.item_count),
            int(row.planned_count),
            int(row.completed_count),
        )
        for row in rows
    }


def _category_counts_by_collection(
    db: Session,
    user: User,
    collection_ids: list[UUID],
) -> dict[UUID, list[dict[str, Any]]]:
    if not collection_ids:
        return {}
    rows = db.execute(
        select(
            Item.collection_id,
            Category.id,
            Category.name,
            func.count().label("item_count"),
        )
        .join(Category, Category.id == Item.category_id)
        .where(
            Item.user_id == user.id,
            Item.collection_id.in_(collection_ids),
        )
        .group_by(Item.collection_id, Category.id, Category.name, Category.sort_order)
        .order_by(Category.sort_order.asc(), Category.name.asc())
    ).all()

    result: dict[UUID, list[dict[str, Any]]] = defaultdict(list)
    for collection_id, category_id, name, item_count in rows:
        result[collection_id].append(
            {
                "id": category_id,
                "name": name,
                "item_count": int(item_count),
            }
        )
    return result


def _collection_dicts(
    db: Session,
    user: User,
    collections: list[Collection],
) -> list[dict[str, Any]]:
    ids = [collection.id for collection in collections]
    status_map = _status_counts_by_collection(db, user, ids)
    category_map = _category_counts_by_collection(db, user, ids)

    payloads: list[dict[str, Any]] = []
    for collection in collections:
        item_count, planned_count, completed_count = status_map.get(collection.id, (0, 0, 0))
        categories = category_map.get(collection.id, [])
        payloads.append(
            {
                "id": collection.id,
                "name": collection.name,
                "item_count": item_count,
                "planned_count": planned_count,
                "completed_count": completed_count,
                "categories": categories,
                "created_at": collection.created_at,
                "updated_at": collection.updated_at,
            }
        )
    return payloads


def list_collections(db: Session, user: User, params: CollectionListParams) -> dict[str, Any]:
    count_stmt = _apply_collection_filters(
        select(func.count()).select_from(Collection),
        user,
        params,
    )
    total = int(db.scalar(count_stmt) or 0)
    total_pages = math.ceil(total / params.page_size) if total else 0
    offset = (params.page - 1) * params.page_size

    list_stmt = _apply_collection_filters(select(Collection), user, params)
    list_stmt = _apply_collection_sort(list_stmt, user, params)
    list_stmt = list_stmt.offset(offset).limit(params.page_size)
    collections = list(db.scalars(list_stmt).all())

    return {
        "collections": _collection_dicts(db, user, collections),
        "page": params.page,
        "page_size": params.page_size,
        "total": total,
        "total_pages": total_pages,
        "has_next": params.page < total_pages,
        "has_previous": params.page > 1 and total > 0,
    }


def get_collection_detail(db: Session, user: User, collection_id: UUID) -> dict[str, Any]:
    collection = db.scalar(
        select(Collection).where(
            Collection.id == collection_id,
            Collection.user_id == user.id,
        )
    )
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        )
    return _collection_dicts(db, user, [collection])[0]
