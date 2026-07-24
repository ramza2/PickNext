import { apiRequest, ApiError } from "./client";
import { buildQueryString } from "./query";
import type { ApiItemDetail } from "../types/api";
import type {
  ItemFromTmdbCreatePayload,
  TmdbAlreadyExistsDetail,
  TmdbDetailResponse,
  TmdbMediaType,
  TmdbSearchMediaFilter,
  TmdbSearchResponse,
  TmdbStatusResponse,
} from "../types/tmdb";

export function getTmdbStatus(signal?: AbortSignal): Promise<TmdbStatusResponse> {
  return apiRequest<TmdbStatusResponse>("/tmdb/status", { signal });
}

export function searchTmdb(
  params: {
    query: string;
    media_type?: TmdbSearchMediaFilter;
    page?: number;
  },
  signal?: AbortSignal,
): Promise<TmdbSearchResponse> {
  const qs = buildQueryString({
    query: params.query,
    media_type: params.media_type,
    page: params.page,
  });
  return apiRequest<TmdbSearchResponse>(`/tmdb/search${qs}`, { signal });
}

export function getTmdbDetails(
  mediaType: TmdbMediaType,
  tmdbId: number,
  signal?: AbortSignal,
): Promise<TmdbDetailResponse> {
  return apiRequest<TmdbDetailResponse>(
    `/tmdb/details/${encodeURIComponent(mediaType)}/${tmdbId}`,
    { signal },
  );
}

export function createItemFromTmdb(
  payload: ItemFromTmdbCreatePayload,
  signal?: AbortSignal,
): Promise<ApiItemDetail> {
  return apiRequest<ApiItemDetail>("/items/from-tmdb", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

export function isTmdbAlreadyExistsDetail(
  detail: unknown,
): detail is TmdbAlreadyExistsDetail {
  if (!detail || typeof detail !== "object") return false;
  const record = detail as Record<string, unknown>;
  return (
    record.code === "TMDB_ITEM_ALREADY_EXISTS"
    && typeof record.existing_item_id === "string"
    && record.existing_item_id.length > 0
  );
}

export function tmdbAlreadyExistsItemId(err: unknown): string | null {
  if (!(err instanceof ApiError) || err.status !== 409) return null;
  if (isTmdbAlreadyExistsDetail(err.detail)) {
    return err.detail.existing_item_id;
  }
  return null;
}
