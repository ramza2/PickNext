from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import ItemStatus, User
from app.schemas import CollectionListResponse, CollectionResponse, CollectionSort, SortOrder
from app.services import catalog
from app.services.catalog import CollectionListParams

router = APIRouter(tags=["collections"])


@router.get("/collections", response_model=CollectionListResponse)
def read_collections(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str | None = Query(None),
    category_id: UUID | None = Query(None),
    status: ItemStatus | None = Query(None),
    sort: CollectionSort = Query(CollectionSort.UPDATED_AT),
    order: SortOrder = Query(SortOrder.DESC),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CollectionListResponse:
    payload = catalog.list_collections(
        db,
        user,
        CollectionListParams(
            page=page,
            page_size=page_size,
            search=search,
            category_id=category_id,
            status=status,
            sort=sort,
            order=order,
        ),
    )
    return CollectionListResponse(**payload)


@router.get("/collections/{collection_id}", response_model=CollectionResponse)
def read_collection_detail(
    collection_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CollectionResponse:
    return CollectionResponse(**catalog.get_collection_detail(db, user, collection_id))


@router.delete(
    "/collections/{collection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
    responses={
        404: {"description": "Collection not found"},
        409: {"description": "Collection contains items"},
        422: {"description": "Validation Error"},
    },
)
def delete_collection(
    collection_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    catalog.delete_collection(db, user, collection_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
