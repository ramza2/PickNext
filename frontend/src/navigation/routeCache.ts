/** In-memory route session cache (cleared on logout/401/user change). */

import type { RecommendStep } from "../types/mock";
import type { RandomRecommendationResponse, RecommendationStatusFilter } from "../types/recommendation";
import type { SearchPageSnapshot } from "../app/search/SearchPage";
import type { ItemsPageStateSnapshot } from "../app/hooks/useItemsReadData";
import type { CollectionsQuerySnapshot } from "../app/hooks/useCollectionsReadData";

export interface RecommendSessionCache {
  step: RecommendStep;
  categoryId: string;
  statusFilter: RecommendationStatusFilter;
  result: RandomRecommendationResponse | null;
  savedHistoryId: string | null;
}

export interface RouteSessionCache {
  itemsSnapshot: ItemsPageStateSnapshot | null;
  collectionsSnapshot: CollectionsQuerySnapshot | null;
  searchSnapshot: SearchPageSnapshot | null;
  recommend: RecommendSessionCache | null;
  scrollByEntryId: Map<string, number>;
}

export function createEmptyRouteCache(): RouteSessionCache {
  return {
    itemsSnapshot: null,
    collectionsSnapshot: null,
    searchSnapshot: null,
    recommend: null,
    scrollByEntryId: new Map(),
  };
}

export function clearRouteCache(cache: RouteSessionCache): void {
  cache.itemsSnapshot = null;
  cache.collectionsSnapshot = null;
  cache.searchSnapshot = null;
  cache.recommend = null;
  cache.scrollByEntryId.clear();
}
