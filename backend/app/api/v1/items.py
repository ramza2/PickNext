from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import ItemStatus, User
from app.schemas import (
    ItemCreate,
    ItemDetailResponse,
    ItemListResponse,
    ItemSort,
    ItemUpdate,
    SortOrder,
)
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


@router.post(
    "/items",
    response_model=ItemDetailResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Category or collection not found"},
        409: {"description": "Related resource changed"},
        422: {"description": "Validation Error"},
    },
)
def create_item(
    payload: ItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ItemDetailResponse:
    return ItemDetailResponse(**catalog.create_item(db, user, payload))


@router.patch(
    "/items/{item_id}",
    response_model=ItemDetailResponse,
    responses={
        404: {"description": "Item or related resource not found"},
        409: {"description": "Related resource changed"},
        422: {"description": "Validation Error"},
    },
)
def update_item(
    item_id: UUID,
    payload: ItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ItemDetailResponse:
    return ItemDetailResponse(**catalog.update_item(db, user, item_id, payload))


@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
    responses={
        404: {"description": "Item not found"},
        409: {"description": "Conflict while deleting item"},
        422: {"description": "Validation Error"},
    },
)
def delete_item(
    item_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    catalog.delete_item(db, user, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
