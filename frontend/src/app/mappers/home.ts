import type { ApiCategory, ApiCategoryType, ApiItemListItem } from "../../types/api";
import {
  getCategoryPresentation,
  type CategoryPresentation,
} from "../presentation/categoryPresentation";

export interface HomeCategoryViewModel {
  id: string;
  name: string;
  categoryType: ApiCategoryType;
  itemCount: number;
  plannedCount: number;
  completedCount: number;
  presentation: CategoryPresentation;
}

export interface HomeRecentItemViewModel {
  id: string;
  title: string;
  status: "PLANNED" | "COMPLETED";
  rating: number;
  progressNote: string | null;
  categoryId: string;
  categoryName: string;
  collectionName: string | null;
  createdAt: string;
  updatedAt: string;
  presentation: CategoryPresentation;
  /** List-summary only; full detail API is Phase B-2c. */
  source: "api-summary";
}

export function mapApiCategoryToHomeCategory(
  category: ApiCategory,
): HomeCategoryViewModel {
  return {
    id: category.id,
    name: category.name,
    categoryType: category.category_type,
    itemCount: category.item_count,
    plannedCount: category.planned_count,
    completedCount: category.completed_count,
    presentation: getCategoryPresentation(category.name),
  };
}

export function mapApiItemToHomeRecentItem(
  item: ApiItemListItem,
): HomeRecentItemViewModel {
  return {
    id: item.id,
    title: item.title,
    status: item.status,
    rating: item.rating,
    progressNote: item.progress_note,
    categoryId: item.category.id,
    categoryName: item.category.name,
    collectionName: item.collection?.name ?? null,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    presentation: getCategoryPresentation(item.category.name),
    source: "api-summary",
  };
}

/** rating === 0.0 means unrated in current Legacy convention. */
export function displayRating(rating: number): number | undefined {
  return rating > 0 ? rating : undefined;
}
