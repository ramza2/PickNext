import { apiRequest } from "./client";
import { buildQueryString } from "./query";
import type {
  ApiCategoriesResponse,
  ApiCollection,
  ApiCollectionListParams,
  ApiCollectionListResponse,
  ApiItemDetail,
  ApiItemListParams,
  ApiItemListResponse,
  ApiSummaryResponse,
} from "../types/api";

export function getSummary(
  signal?: AbortSignal,
): Promise<ApiSummaryResponse> {
  return apiRequest<ApiSummaryResponse>("/summary", { signal });
}

export function getCategories(
  signal?: AbortSignal,
): Promise<ApiCategoriesResponse> {
  return apiRequest<ApiCategoriesResponse>("/categories", { signal });
}

export function getItems(
  params?: ApiItemListParams,
  signal?: AbortSignal,
): Promise<ApiItemListResponse> {
  const qs = buildQueryString({
    page: params?.page,
    page_size: params?.page_size,
    search: params?.search,
    category_id: params?.category_id,
    status: params?.status,
    collection_id: params?.collection_id,
    has_collection: params?.has_collection,
    sort: params?.sort,
    order: params?.order,
  });
  return apiRequest<ApiItemListResponse>(`/items${qs}`, { signal });
}

export function getItem(
  itemId: string,
  signal?: AbortSignal,
): Promise<ApiItemDetail> {
  return apiRequest<ApiItemDetail>(
    `/items/${encodeURIComponent(itemId)}`,
    { signal },
  );
}

export function getCollections(
  params?: ApiCollectionListParams,
  signal?: AbortSignal,
): Promise<ApiCollectionListResponse> {
  const qs = buildQueryString({
    page: params?.page,
    page_size: params?.page_size,
    search: params?.search,
    category_id: params?.category_id,
    status: params?.status,
    sort: params?.sort,
    order: params?.order,
  });
  return apiRequest<ApiCollectionListResponse>(`/collections${qs}`, { signal });
}

export function getCollection(
  collectionId: string,
  signal?: AbortSignal,
): Promise<ApiCollection> {
  return apiRequest<ApiCollection>(
    `/collections/${encodeURIComponent(collectionId)}`,
    { signal },
  );
}

export function deleteItem(
  itemId: string,
  signal?: AbortSignal,
): Promise<void> {
  return apiRequest<void>(`/items/${encodeURIComponent(itemId)}`, {
    method: "DELETE",
    signal,
  });
}

export function deleteCollection(
  collectionId: string,
  signal?: AbortSignal,
): Promise<void> {
  return apiRequest<void>(
    `/collections/${encodeURIComponent(collectionId)}`,
    {
      method: "DELETE",
      signal,
    },
  );
}

export interface CollectionWritePayload {
  name: string;
}

export function createCollection(
  payload: CollectionWritePayload,
  signal?: AbortSignal,
): Promise<ApiCollection> {
  return apiRequest<ApiCollection>("/collections", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

export function updateCollection(
  collectionId: string,
  payload: CollectionWritePayload,
  signal?: AbortSignal,
): Promise<ApiCollection> {
  return apiRequest<ApiCollection>(
    `/collections/${encodeURIComponent(collectionId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
      signal,
    },
  );
}
