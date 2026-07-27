import { apiRequest } from "./client";
import { buildQueryString } from "./query";
import type {
  CreateRecommendationHistoryRequest,
  RecommendationHistoryDeleteAllResponse,
  RecommendationHistoryDetail,
  RecommendationHistoryPage,
} from "../types/recommendation";

export function getRecommendationHistory(
  params?: { page?: number; page_size?: number },
  signal?: AbortSignal,
): Promise<RecommendationHistoryPage> {
  const qs = buildQueryString({
    page: params?.page,
    page_size: params?.page_size,
  });
  return apiRequest<RecommendationHistoryPage>(`/recommendation-history${qs}`, {
    signal,
  });
}

export function getRecommendationHistoryDetail(
  historyId: string,
  signal?: AbortSignal,
): Promise<RecommendationHistoryDetail> {
  return apiRequest<RecommendationHistoryDetail>(
    `/recommendation-history/${encodeURIComponent(historyId)}`,
    { signal },
  );
}

export function createRecommendationHistory(
  body: CreateRecommendationHistoryRequest,
  signal?: AbortSignal,
): Promise<RecommendationHistoryDetail> {
  return apiRequest<RecommendationHistoryDetail>("/recommendation-history", {
    method: "POST",
    body: JSON.stringify(body),
    signal,
  });
}

export function deleteRecommendationHistory(
  historyId: string,
  signal?: AbortSignal,
): Promise<void> {
  return apiRequest<void>(
    `/recommendation-history/${encodeURIComponent(historyId)}`,
    { method: "DELETE", signal },
  );
}

export function deleteAllRecommendationHistory(
  signal?: AbortSignal,
): Promise<RecommendationHistoryDeleteAllResponse> {
  return apiRequest<RecommendationHistoryDeleteAllResponse>(
    "/recommendation-history",
    { method: "DELETE", signal },
  );
}
