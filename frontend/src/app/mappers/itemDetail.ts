import type { ApiItemDetail } from "../../types/api";
import {
  getCategoryPresentation,
  type CategoryPresentation,
} from "../presentation/categoryPresentation";

export interface ItemDetailViewModel {
  id: string;
  title: string;
  status: "PLANNED" | "COMPLETED";
  rating: number;
  categoryId: string;
  categoryName: string;
  collectionId: string | null;
  collectionName: string | null;
  progressNote: string | null;
  memo: string | null;
  createdAt: string;
  updatedAt: string;
    releaseYear: number | null;
  posterUrl: string | null;
  synopsis: string | null;
  presentation: CategoryPresentation;
}

export function mapApiItemDetailToViewModel(
  item: ApiItemDetail,
): ItemDetailViewModel {
  return {
    id: item.id,
    title: item.title,
    status: item.status,
    rating: item.rating,
    categoryId: item.category.id,
    categoryName: item.category.name,
    collectionId: item.collection?.id ?? null,
    collectionName: item.collection?.name ?? null,
    progressNote: item.progress_note,
    memo: item.memo,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    releaseYear: item.release_year ?? null,
    posterUrl: item.poster_url ?? null,
    synopsis: item.synopsis ?? null,
    presentation: getCategoryPresentation(item.category.name),
  };
}

/** rating === 0.0 means unrated in current Legacy convention. */
export function displayDetailRating(rating: number): number | undefined {
  return rating > 0 ? rating : undefined;
}
