import type { ApiCategoryRef, ApiCollectionRef, ApiItemListItem, ApiItemStatus } from "./api";

export type RecommendationStatusFilter = "PLANNED" | "COMPLETED" | "ALL";
export type RecommendationCandidateType = "ITEM" | "COLLECTION";

export interface RandomRecommendationRequest {
  category_id: string;
  status_filter: RecommendationStatusFilter;
}

export interface RandomRecommendationResponse {
  category: ApiCategoryRef;
  status_filter: RecommendationStatusFilter;
  candidate_type: RecommendationCandidateType | null;
  candidate_id: string | null;
  collection: ApiCollectionRef | null;
  items: ApiItemListItem[];
  eligible_candidate_count: number;
}

export interface CreateRecommendationHistoryRequest {
  category_id: string;
  status_filter: RecommendationStatusFilter;
  candidate_type: RecommendationCandidateType;
  candidate_id: string;
}

export interface RecommendationHistoryListItem {
  id: string;
  category: ApiCategoryRef;
  status_filter: RecommendationStatusFilter;
  collection: ApiCollectionRef | null;
  selected_at: string;
  title: string;
  item_count: number;
  poster_url: string | null;
  release_year: number | null;
  candidate_type: RecommendationCandidateType;
}

export interface RecommendationHistoryPage {
  items: RecommendationHistoryListItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface RecommendationHistoryDetailItem {
  item_id: string;
  title_snapshot: string;
  status_at_selection: ApiItemStatus;
  sort_order: number;
  item_exists: boolean;
  current: ApiItemListItem | null;
}

export interface RecommendationHistoryDetail {
  id: string;
  category: ApiCategoryRef;
  status_filter: RecommendationStatusFilter;
  collection: ApiCollectionRef | null;
  selected_at: string;
  candidate_type: RecommendationCandidateType;
  items: RecommendationHistoryDetailItem[];
}

export interface RecommendationHistoryDeleteAllResponse {
  deleted_count: number;
}
