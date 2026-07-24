import type {
  TmdbSearchMediaFilter,
  TmdbSearchResultItem,
  TmdbStatusResponse,
} from "../../types/tmdb";

export interface SearchPageSnapshot {
  queryInput: string;
  appliedQuery: string;
  mediaType: TmdbSearchMediaFilter;
  page: number;
  status: TmdbStatusResponse | null;
  results: TmdbSearchResultItem[];
  upstreamTotalPages: number;
  upstreamTotalResults: number;
  hasSearched: boolean;
}

export const EMPTY_SEARCH_SNAPSHOT: SearchPageSnapshot = {
  queryInput: "",
  appliedQuery: "",
  mediaType: "all",
  page: 1,
  status: null,
  results: [],
  upstreamTotalPages: 0,
  upstreamTotalResults: 0,
  hasSearched: false,
};
