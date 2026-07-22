from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import ItemStatus, User
from app.schemas import ItemDetailResponse, ItemListResponse, ItemSort, SortOrder
from app.services import catalog
from app.services.catalog import ItemListParams

router = APIRouter(tags=["items"])


@router.get("/items", response_model=ItemListResponse)
def read_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str | None = Query(None),
    category_id: UUID | None = Query(None),
    status: ItemStatus | None = Query(None),
    collection_id: UUID | None = Query(None),
    has_collection: bool | None = Query(None),
    sort: ItemSort = Query(ItemSort.UPDATED_AT),
    order: SortOrder = Query(SortOrder.DESC),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ItemListResponse:
    payload = catalog.list_items(
        db,
        user,
        ItemListParams(
            page=page,
            page_size=page_size,
            search=search,
            category_id=category_id,
            status=status,
            collection_id=collection_id,
            has_collection=has_collection,
            sort=sort,
            order=order,
        ),
    )
    return ItemListResponse(**payload)


@router.get("/items/{item_id}", response_model=ItemDetailResponse)
def read_item_detail(
    item_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ItemDetailResponse:
    return ItemDetailResponse(**catalog.get_item_detail(db, user, item_id))
