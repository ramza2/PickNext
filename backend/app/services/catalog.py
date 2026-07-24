"""Catalog queries: summary, categories, items, collections (read + delete)."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Select, asc, delete, desc, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Category,
    Collection,
    Item,
    ItemStatus,
    RecommendationHistory,
    RecommendationHistoryItem,
    User,
)

if TYPE_CHECKING:
    from app.schemas import ItemCreate, ItemFromTmdbCreate, ItemUpdate

EXTERNAL_SOURCE_TMDB = "tmdb"
TMDB_ITEM_ALREADY_EXISTS = "TMDB_ITEM_ALREADY_EXISTS"


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


def _get_owned_category(db: Session, user_id: UUID, category_id: UUID) -> Category | None:
    return db.scalar(
        select(Category).where(
            Category.id == category_id,
            Category.user_id == user_id,
        )
    )


def _lock_owned_collection(db: Session, user_id: UUID, collection_id: UUID) -> Collection | None:
    return db.scalar(
        select(Collection)
        .where(
            Collection.id == collection_id,
            Collection.user_id == user_id,
        )
        .with_for_update()
    )


def _lock_owned_collections_ordered(
    db: Session,
    user_id: UUID,
    collection_ids: set[UUID],
) -> None:
    for collection_id in sorted(collection_ids, key=str):
        if _lock_owned_collection(db, user_id, collection_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collection not found",
            )


def _ensure_item_collection_integrity(db: Session, user_id: UUID, collection_id: UUID) -> None:
    collection = db.get(Collection, collection_id)
    if collection is None or collection.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Data integrity error",
        )


def _fetch_item_detail_row(db: Session, user_id: UUID, item_id: UUID) -> Item:
    item = db.scalar(
        select(Item)
        .options(
            joinedload(Item.category),
            joinedload(Item.collection),
        )
        .where(
            Item.id == item_id,
            Item.user_id == user_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


def _item_detail_dict(item: Item) -> dict[str, Any]:
    payload = _item_list_dict(item)
    payload["memo"] = item.memo
    return payload


def _item_field_values_equal(field: str, current: Any, new: Any) -> bool:
    if field == "rating":
        return Decimal(str(current)) == Decimal(str(new))
    return current == new


def _is_known_item_write_integrity_error(exc: IntegrityError) -> bool:
    orig = getattr(exc, "orig", None)
    known = {
        "items_category_id_fkey",
        "items_collection_id_fkey",
    }
    if orig is not None:
        constraint = getattr(orig, "constraint_name", None)
        if constraint in known:
            return True
        diag = getattr(orig, "diag", None)
        if diag is not None:
            diag_constraint = getattr(diag, "constraint_name", None)
            if diag_constraint in known:
                return True
    message = str(exc)
    return "items_category_id_fkey" in message or "items_collection_id_fkey" in message


def _is_external_identity_unique_violation(exc: IntegrityError) -> bool:
    name = "uq_items_user_external_identity"
    orig = getattr(exc, "orig", None)
    if orig is not None:
        constraint = getattr(orig, "constraint_name", None)
        if constraint == name:
            return True
        diag = getattr(orig, "diag", None)
        if diag is not None:
            diag_constraint = getattr(diag, "constraint_name", None)
            if diag_constraint == name:
                return True
    return name in str(exc)


def find_item_by_tmdb_identity(
    db: Session,
    user_id: UUID,
    *,
    media_type: str,
    tmdb_id: int,
) -> Item | None:
    return db.scalar(
        select(Item).where(
            Item.user_id == user_id,
            Item.external_source == EXTERNAL_SOURCE_TMDB,
            Item.external_media_type == media_type,
            Item.external_id == str(tmdb_id),
        )
    )


def _raise_tmdb_item_already_exists(existing_item_id: UUID) -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": TMDB_ITEM_ALREADY_EXISTS,
            "existing_item_id": str(existing_item_id),
        },
    )


def create_item(
    db: Session,
    user: User,
    payload: ItemCreate,
    *,
    commit: bool = True,
) -> dict[str, Any]:
    """Create an item for the user."""
    if _get_owned_category(db, user.id, payload.category_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    if payload.collection_id is not None:
        _lock_owned_collections_ordered(db, user.id, {payload.collection_id})

    item = Item(
        user_id=user.id,
        category_id=payload.category_id,
        collection_id=payload.collection_id,
        title=payload.title,
        status=payload.status,
        rating=payload.rating,
        progress_note=payload.progress_note,
        memo=payload.memo,
    )
    try:
        db.add(item)
        db.flush()
        response = _item_detail_dict(_fetch_item_detail_row(db, user.id, item.id))
        if commit:
            db.commit()
        return response
    except HTTPException:
        if commit:
            db.rollback()
        raise
    except IntegrityError as exc:
        if commit:
            db.rollback()
        if _is_known_item_write_integrity_error(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Related resource changed",
            ) from exc
        raise
    except Exception:
        if commit:
            db.rollback()
        raise


def create_item_from_tmdb(
    db: Session,
    user: User,
    payload: ItemFromTmdbCreate,
    *,
    trusted_title: str,
    original_title: str | None,
    original_language: str | None,
    poster_path: str | None,
    backdrop_path: str | None,
    commit: bool = True,
) -> dict[str, Any]:
    """Create an item with server-trusted TMDB external identity fields.

    Callers must re-fetch TMDB detail and pass metadata here; client-supplied
    external fields are never accepted on the request schema.
    """
    existing = find_item_by_tmdb_identity(
        db,
        user.id,
        media_type=payload.media_type,
        tmdb_id=payload.tmdb_id,
    )
    if existing is not None:
        _raise_tmdb_item_already_exists(existing.id)

    if _get_owned_category(db, user.id, payload.category_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    if payload.collection_id is not None:
        _lock_owned_collections_ordered(db, user.id, {payload.collection_id})

    title = payload.title if payload.title is not None else trusted_title
    if not title or not title.strip():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TMDB_UPSTREAM_ERROR",
        )

    item = Item(
        user_id=user.id,
        category_id=payload.category_id,
        collection_id=payload.collection_id,
        title=title.strip(),
        status=payload.status,
        rating=payload.rating,
        progress_note=payload.progress_note,
        memo=payload.memo,
        external_source=EXTERNAL_SOURCE_TMDB,
        external_id=str(payload.tmdb_id),
        external_media_type=payload.media_type,
        original_title=original_title,
        original_language=original_language,
        poster_path=poster_path,
        backdrop_path=backdrop_path,
        external_metadata_updated_at=datetime.now(timezone.utc),
    )
    try:
        db.add(item)
        db.flush()
        response = _item_detail_dict(_fetch_item_detail_row(db, user.id, item.id))
        if commit:
            db.commit()
        return response
    except HTTPException:
        if commit:
            db.rollback()
        raise
    except IntegrityError as exc:
        if commit:
            db.rollback()
        if _is_external_identity_unique_violation(exc):
            raced = find_item_by_tmdb_identity(
                db,
                user.id,
                media_type=payload.media_type,
                tmdb_id=payload.tmdb_id,
            )
            if raced is not None:
                _raise_tmdb_item_already_exists(raced.id)
        if _is_known_item_write_integrity_error(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Related resource changed",
            ) from exc
        raise
    except Exception:
        if commit:
            db.rollback()
        raise


def update_item(
    db: Session,
    user: User,
    item_id: UUID,
    payload: ItemUpdate,
    *,
    commit: bool = True,
) -> dict[str, Any]:
    """Partially update an item owned by the user."""
    item = db.scalar(
        select(Item).where(Item.id == item_id, Item.user_id == user.id).with_for_update()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    if item.collection_id is not None:
        _ensure_item_collection_integrity(db, user.id, item.collection_id)

    fields = payload.model_fields_set
    new_values: dict[str, Any] = {}

    if "title" in fields:
        new_values["title"] = payload.title
    if "category_id" in fields:
        if _get_owned_category(db, user.id, payload.category_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found",
            )
        new_values["category_id"] = payload.category_id
    if "status" in fields:
        new_values["status"] = payload.status
    if "rating" in fields:
        new_values["rating"] = payload.rating
    if "progress_note" in fields:
        new_values["progress_note"] = payload.progress_note
    if "memo" in fields:
        new_values["memo"] = payload.memo
    if "collection_id" in fields:
        new_collection_id = payload.collection_id
        old_collection_id = item.collection_id
        if new_collection_id != old_collection_id:
            lock_ids = {
                collection_id
                for collection_id in (old_collection_id, new_collection_id)
                if collection_id is not None
            }
            if lock_ids:
                _lock_owned_collections_ordered(db, user.id, lock_ids)
        new_values["collection_id"] = new_collection_id

    changed = any(
        not _item_field_values_equal(field, getattr(item, field), value)
        for field, value in new_values.items()
    )

    if not changed:
        if commit:
            db.commit()
        return _item_detail_dict(_fetch_item_detail_row(db, user.id, item.id))

    for field, value in new_values.items():
        setattr(item, field, value)

    try:
        db.flush()
        response = _item_detail_dict(_fetch_item_detail_row(db, user.id, item.id))
        if commit:
            db.commit()
        return response
    except HTTPException:
        if commit:
            db.rollback()
        raise
    except IntegrityError as exc:
        if commit:
            db.rollback()
        if _is_known_item_write_integrity_error(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Related resource changed",
            ) from exc
        raise
    except Exception:
        if commit:
            db.rollback()
        raise


def delete_item(
    db: Session,
    user: User,
    item_id: UUID,
    *,
    commit: bool = True,
) -> None:
    """Hard-delete an item with recommendation history and last-collection cleanup.

    Transaction order (single commit when ``commit=True``):
    1. Item SELECT FOR UPDATE
    2. Collection SELECT FOR UPDATE when collection_id is set
    3. Distinct recommendation_history IDs for the item
    4. Delete those RecommendationHistory parents (items CASCADE)
    5. Delete Item (legacy_import_items CASCADE)
    6. EXISTS remaining items in original collection
    7. Delete Collection when empty

    Future Item POST/PATCH that attach a collection should lock the same
    Collection row (FOR UPDATE) after validating ownership to serialize with
    this path.

    ``commit=False`` is for tests that wrap mutations in their own SAVEPOINT.
    """
    item = db.scalar(
        select(Item).where(Item.id == item_id, Item.user_id == user.id).with_for_update()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    original_collection_id = item.collection_id
    collection: Collection | None = None
    if original_collection_id is not None:
        collection = db.scalar(
            select(Collection)
            .where(
                Collection.id == original_collection_id,
                Collection.user_id == user.id,
            )
            .with_for_update()
        )
        if collection is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Data integrity error",
            )

    try:
        history_ids = list(
            db.scalars(
                select(RecommendationHistoryItem.recommendation_history_id)
                .where(RecommendationHistoryItem.item_id == item.id)
                .distinct()
            ).all()
        )
        if history_ids:
            owned_ids = set(
                db.scalars(
                    select(RecommendationHistory.id).where(
                        RecommendationHistory.id.in_(history_ids),
                        RecommendationHistory.user_id == user.id,
                    )
                ).all()
            )
            if owned_ids != set(history_ids):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Data integrity error",
                )
            db.execute(
                delete(RecommendationHistory).where(
                    RecommendationHistory.id.in_(history_ids),
                    RecommendationHistory.user_id == user.id,
                )
            )
            db.flush()

        db.delete(item)
        db.flush()

        if original_collection_id is not None and collection is not None:
            has_remaining = db.scalar(
                select(
                    exists().where(
                        Item.collection_id == original_collection_id,
                        Item.user_id == user.id,
                    )
                )
            )
            if not has_remaining:
                db.delete(collection)
                db.flush()

        if commit:
            db.commit()
    except HTTPException:
        raise
    except IntegrityError:
        if commit:
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict while deleting item",
        ) from None
    except Exception:
        if commit:
            db.rollback()
        raise


def delete_collection(
    db: Session,
    user: User,
    collection_id: UUID,
    *,
    commit: bool = True,
) -> None:
    """Hard-delete an empty collection owned by the user.

    Transaction order (single commit when ``commit=True``):
    1. Collection SELECT FOR UPDATE
    2. Item EXISTS (any row referencing collection_id)
    3. Collection DELETE when no items (legacy_import_collections CASCADE;
       recommendation_history.collection_id SET NULL via DB FK)

    Item POST/PATCH that attach or move to a collection should lock the target
    Collection row (FOR UPDATE) after validating ownership to serialize with
    this path and Item DELETE.

    ``commit=False`` is for tests that wrap mutations in their own SAVEPOINT.
    """
    collection = db.scalar(
        select(Collection)
        .where(Collection.id == collection_id, Collection.user_id == user.id)
        .with_for_update()
    )
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        )

    has_items = db.scalar(select(exists().where(Item.collection_id == collection_id)))
    if has_items:
        wrong_owner = db.scalar(
            select(
                exists().where(
                    Item.collection_id == collection_id,
                    Item.user_id != collection.user_id,
                )
            )
        )
        if wrong_owner:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Data integrity error",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Collection contains items",
        )

    try:
        db.delete(collection)
        db.flush()
        if commit:
            db.commit()
    except HTTPException:
        raise
    except IntegrityError:
        if commit:
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Collection contains items",
        ) from None
    except Exception:
        if commit:
            db.rollback()
        raise


def _is_collection_name_unique_violation(exc: IntegrityError) -> bool:
    orig = getattr(exc, "orig", None)
    if orig is not None:
        constraint = getattr(orig, "constraint_name", None)
        if constraint == "uq_collections_user_id_name":
            return True
        diag = getattr(orig, "diag", None)
        if diag is not None:
            diag_constraint = getattr(diag, "constraint_name", None)
            if diag_constraint == "uq_collections_user_id_name":
                return True
    return "uq_collections_user_id_name" in str(exc)


def create_collection(
    db: Session,
    user: User,
    name: str,
    *,
    commit: bool = True,
) -> dict[str, Any]:
    """Create an empty collection for the user."""
    existing_id = db.scalar(
        select(Collection.id).where(
            Collection.user_id == user.id,
            Collection.name == name,
        )
    )
    if existing_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Collection name already exists",
        )

    collection = Collection(user_id=user.id, name=name)
    try:
        db.add(collection)
        db.flush()
        response = _collection_dicts(db, user, [collection])[0]
        if commit:
            db.commit()
        return response
    except HTTPException:
        if commit:
            db.rollback()
        raise
    except IntegrityError as exc:
        if commit:
            db.rollback()
        if _is_collection_name_unique_violation(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Collection name already exists",
            ) from exc
        raise
    except Exception:
        if commit:
            db.rollback()
        raise


def update_collection(
    db: Session,
    user: User,
    collection_id: UUID,
    name: str,
    *,
    commit: bool = True,
) -> dict[str, Any]:
    """Rename a collection owned by the user."""
    collection = db.scalar(
        select(Collection)
        .where(Collection.id == collection_id, Collection.user_id == user.id)
        .with_for_update()
    )
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        )

    if collection.name == name:
        if commit:
            db.commit()
        return _collection_dicts(db, user, [collection])[0]

    conflict_id = db.scalar(
        select(Collection.id).where(
            Collection.user_id == user.id,
            Collection.name == name,
            Collection.id != collection_id,
        )
    )
    if conflict_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Collection name already exists",
        )

    collection.name = name
    try:
        db.flush()
        response = _collection_dicts(db, user, [collection])[0]
        if commit:
            db.commit()
        return response
    except HTTPException:
        if commit:
            db.rollback()
        raise
    except IntegrityError as exc:
        if commit:
            db.rollback()
        if _is_collection_name_unique_violation(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Collection name already exists",
            ) from exc
        raise
    except Exception:
        if commit:
            db.rollback()
        raise


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
        "external_source": item.external_source,
        "external_id": item.external_id,
        "external_media_type": item.external_media_type,
        "original_title": item.original_title,
        "original_language": item.original_language,
        "poster_path": item.poster_path,
        "backdrop_path": item.backdrop_path,
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
