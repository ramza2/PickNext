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

export interface ItemCreatePayload {
  title: string;
  category_id: string;
  collection_id?: string | null;
  status?: "PLANNED" | "COMPLETED";
  rating?: number;
  progress_note?: string | null;
  memo?: string | null;
  release_year?: number | null;
  synopsis?: string | null;
}

export interface ItemUpdatePayload {
  title?: string;
  category_id?: string;
  collection_id?: string | null;
  status?: "PLANNED" | "COMPLETED";
  rating?: number;
  progress_note?: string | null;
  memo?: string | null;
  release_year?: number | null;
  synopsis?: string | null;
}

export function createItem(
  payload: ItemCreatePayload,
  signal?: AbortSignal,
): Promise<ApiItemDetail> {
  return apiRequest<ApiItemDetail>("/items", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

export function updateItem(
  itemId: string,
  payload: ItemUpdatePayload,
  signal?: AbortSignal,
): Promise<ApiItemDetail> {
  return apiRequest<ApiItemDetail>(
    `/items/${encodeURIComponent(itemId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
      signal,
    },
  );
}

/** Load all collections for Item Form select (paginated API). */
export async function getAllCollectionsForSelect(
  signal?: AbortSignal,
): Promise<ApiCollection[]> {
  const pageSize = 100;
  const first = await getCollections(
    { page: 1, page_size: pageSize, sort: "name", order: "asc" },
    signal,
  );
  const byId = new Map<string, ApiCollection>();
  for (const row of first.collections) {
    byId.set(row.id, row);
  }
  const totalPages = first.total_pages ?? 0;
  for (let page = 2; page <= totalPages; page += 1) {
    const next = await getCollections(
      { page, page_size: pageSize, sort: "name", order: "asc" },
      signal,
    );
    for (const row of next.collections) {
      byId.set(row.id, row);
    }
  }
  return Array.from(byId.values());
}
