export type ApiItemStatus = "PLANNED" | "COMPLETED";

export type ApiCategoryType =
  | "MEDIA"
  | "BOOK"
  | "FOOD"
  | "GENERAL";

export type ApiItemSort =
  | "updated_at"
  | "created_at"
  | "title"
  | "rating"
  | "status";

export type ApiSortOrder = "asc" | "desc";

export interface ApiSummaryResponse {
  item_count: number;
  planned_count: number;
  completed_count: number;
  collection_count: number;
  category_count: number;
}

export interface ApiCategory {
  id: string;
  name: string;
  category_type: ApiCategoryType;
  sort_order: number;
  item_count: number;
  planned_count: number;
  completed_count: number;
}

export interface ApiCategoriesResponse {
  categories: ApiCategory[];
}

export interface ApiCategoryRef {
  id: string;
  name: string;
}

export interface ApiCollectionRef {
  id: string;
  name: string;
}

export interface ApiItemListItem {
  id: string;
  title: string;
  status: ApiItemStatus;
  rating: number;
  progress_note: string | null;
  category: ApiCategoryRef;
  collection: ApiCollectionRef | null;
  created_at: string;
  updated_at: string;
  external_source?: string | null;
  external_id?: string | null;
  external_media_type?: string | null;
  original_title?: string | null;
  original_language?: string | null;
  poster_path?: string | null;
  backdrop_path?: string | null;
}

export interface ApiItemDetail extends ApiItemListItem {
  memo: string | null;
}

export interface ApiItemListResponse {
  items: ApiItemListItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export type ApiCollectionSort =
  | "updated_at"
  | "created_at"
  | "name"
  | "item_count"
  | "completed_count";

export interface ApiCollectionCategoryCount {
  id: string;
  name: string;
  item_count: number;
}

export interface ApiCollection {
  id: string;
  name: string;
  item_count: number;
  planned_count: number;
  completed_count: number;
  categories: ApiCollectionCategoryCount[];
  created_at: string;
  updated_at: string;
}

export interface ApiCollectionListResponse {
  collections: ApiCollection[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface ApiCollectionListParams {
  page?: number;
  page_size?: number;
  search?: string;
  category_id?: string;
  status?: ApiItemStatus;
  sort?: ApiCollectionSort;
  order?: ApiSortOrder;
}

export interface ApiItemListParams {
  page?: number;
  page_size?: number;
  search?: string;
  category_id?: string;
  status?: ApiItemStatus;
  collection_id?: string;
  has_collection?: boolean;
  sort?: ApiItemSort;
  order?: ApiSortOrder;
}
