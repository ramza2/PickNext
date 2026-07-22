import type { LucideIcon } from "lucide-react";
import {
  Film,
  Tv,
  BookOpen,
  Utensils,
  Smile,
  Tag,
} from "lucide-react";

/**
 * UI presentation metadata only.
 * Category identity and counts come from the Backend API.
 * Do not use Mock slug IDs (`movie`, `kdrama`, …) as relationship keys.
 */
export interface CategoryPresentation {
  icon: LucideIcon;
  color: string;
  bgColor: string;
}

const CATEGORY_PRESENTATION_BY_NAME: Record<string, CategoryPresentation> = {
  영화: { icon: Film, color: "#3B82F6", bgColor: "#EFF6FF" },
  한국드라마: { icon: Tv, color: "#8B5CF6", bgColor: "#F5F3FF" },
  일본드라마: { icon: Tv, color: "#F97316", bgColor: "#FFF7ED" },
  미국드라마: { icon: Tv, color: "#EF4444", bgColor: "#FEF2F2" },
  중국드라마: { icon: Tv, color: "#EC4899", bgColor: "#FDF2F8" },
  애니메이션: { icon: Smile, color: "#6366F1", bgColor: "#EEF2FF" },
  "애니 영화": { icon: Film, color: "#7C3AED", bgColor: "#F5F3FF" },
  예능: { icon: Smile, color: "#D97706", bgColor: "#FFFBEB" },
  만화책: { icon: BookOpen, color: "#10B981", bgColor: "#ECFDF5" },
  음식: { icon: Utensils, color: "#F59E0B", bgColor: "#FFFBEB" },
};

const FALLBACK_PRESENTATION: CategoryPresentation = {
  icon: Tag,
  color: "#6B7280",
  bgColor: "#F3F4F6",
};

export function getCategoryPresentation(name: string): CategoryPresentation {
  return CATEGORY_PRESENTATION_BY_NAME[name] ?? FALLBACK_PRESENTATION;
}

/** Quick-recommend presets: meaning by Category name (not Mock slug). */
export const QUICK_RECOMMENDATION_PRESETS = {
  movie: ["영화"],
  drama: ["한국드라마", "일본드라마", "중국드라마", "미국드라마"],
  animation: ["애니메이션", "애니 영화"],
  variety: ["예능"],
  book: ["만화책"],
  food: ["음식"],
} as const;

/**
 * Resolve Category names → Backend UUIDs.
 * Reserved for future recommendation API; B-2a does not call recommend APIs.
 */
export function resolveCategoryIds(
  categoryNames: readonly string[],
  categories: { id: string; name: string }[],
): string[] {
  const byName = new Map(categories.map((c) => [c.name, c.id]));
  return categoryNames
    .map((name) => byName.get(name))
    .filter((id): id is string => Boolean(id));
}
