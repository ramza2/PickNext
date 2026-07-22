import { apiRequest } from "./client";
import { buildQueryString } from "./query";
import type {
  ApiCategoriesResponse,
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
