import type { ApiItemListItem } from "../../types/api";
import {
  getCategoryPresentation,
  type CategoryPresentation,
} from "../presentation/categoryPresentation";

export interface ItemsListViewModel {
  id: string;
  title: string;
  status: "PLANNED" | "COMPLETED";
  rating: number;
  progressNote: string | null;
  categoryId: string;
  categoryName: string;
  collectionId: string | null;
  collectionName: string | null;
  createdAt: string;
  updatedAt: string;
  presentation: CategoryPresentation;
}

export function mapApiItemToItemsListViewModel(
  item: ApiItemListItem,
): ItemsListViewModel {
  return {
    id: item.id,
    title: item.title,
    status: item.status,
    rating: item.rating,
    progressNote: item.progress_note,
    categoryId: item.category.id,
    categoryName: item.category.name,
    collectionId: item.collection?.id ?? null,
    collectionName: item.collection?.name ?? null,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    presentation: getCategoryPresentation(item.category.name),
  };
}

/** rating === 0.0 means unrated in current Legacy convention. */
export function displayItemRating(rating: number): number | undefined {
  return rating > 0 ? rating : undefined;
}
