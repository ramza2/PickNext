import type { ApiCollection } from "../../types/api";
import {
  getCategoryPresentation,
  type CategoryPresentation,
} from "../presentation/categoryPresentation";

export interface CollectionCategoryViewModel {
  id: string;
  name: string;
  itemCount: number;
  presentation: CategoryPresentation;
}

export interface CollectionListItemViewModel {
  id: string;
  name: string;
  itemCount: number;
  plannedCount: number;
  completedCount: number;
  categories: CollectionCategoryViewModel[];
  /** 0–100, rounded for ProgressBar display. */
  progressPercent: number;
  /** Backend Collection API does not provide avg_rating. */
  averageRating: null;
  createdAt: string;
  updatedAt: string;
}

/** Same schema as list; alias for detail screens. */
export type CollectionDetailViewModel = CollectionListItemViewModel;

export function computeCollectionProgressPercent(
  itemCount: number,
  completedCount: number,
): number {
  if (!Number.isFinite(itemCount) || itemCount <= 0) return 0;
  if (!Number.isFinite(completedCount) || completedCount <= 0) return 0;
  return Math.round((completedCount / itemCount) * 100);
}

export function mapApiCollectionToListItem(
  collection: ApiCollection,
): CollectionListItemViewModel {
  return {
    id: collection.id,
    name: collection.name,
    itemCount: collection.item_count,
    plannedCount: collection.planned_count,
    completedCount: collection.completed_count,
    categories: collection.categories.map((category) => ({
      id: category.id,
      name: category.name,
      itemCount: category.item_count,
      presentation: getCategoryPresentation(category.name),
    })),
    progressPercent: computeCollectionProgressPercent(
      collection.item_count,
      collection.completed_count,
    ),
    averageRating: null,
    createdAt: collection.created_at,
    updatedAt: collection.updated_at,
  };
}

export const mapApiCollectionToDetail = mapApiCollectionToListItem;

/** Pure helper for Collection 소속 Item 목록 호출 파라미터. page_size는 기본값 사용(미전달). */
export function buildCollectionItemsQueryParams(
  collectionId: string,
  page: number,
): {
  collection_id: string;
  sort: "title";
  order: "asc";
  page: number;
} {
  return {
    collection_id: collectionId,
    sort: "title",
    order: "asc",
    page,
  };
}
