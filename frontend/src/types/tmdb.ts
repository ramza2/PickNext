/** TMDB API types — aligned with backend `app.schemas.tmdb` + ItemFromTmdbCreate. */

export type TmdbMediaType = "movie" | "tv";
export type TmdbSearchMediaFilter = "all" | "movie" | "tv";
export type TmdbStatusValue = "AVAILABLE" | "NOT_CONFIGURED" | "UNAVAILABLE";
export type TmdbAuthMode = "bearer" | "api_key" | "none";

export interface TmdbStatusResponse {
  status: TmdbStatusValue;
  configured: boolean;
  available: boolean;
  auth_mode: TmdbAuthMode;
  language: string;
  region: string;
  checked_at: string;
}

export interface TmdbGenre {
  id: number;
  name: string;
}

export interface TmdbCastMember {
  tmdb_person_id: number;
  name: string;
  character: string | null;
  profile_path: string | null;
  profile_url: string | null;
  order: number | null;
}

export interface TmdbCrewMember {
  tmdb_person_id: number;
  name: string;
  job: string | null;
  profile_path: string | null;
  profile_url: string | null;
}

export interface TmdbExternalIds {
  imdb_id: string | null;
  wikidata_id: string | null;
  facebook_id: string | null;
  instagram_id: string | null;
  twitter_id: string | null;
}

export interface TmdbSearchResultItem {
  tmdb_id: number;
  media_type: TmdbMediaType;
  title: string;
  original_title: string | null;
  overview: string | null;
  original_language: string | null;
  release_date: string | null;
  release_year: number | null;
  genre_ids: number[];
  poster_path: string | null;
  poster_url: string | null;
  backdrop_path: string | null;
  backdrop_url: string | null;
  adult: boolean | null;
  popularity: number | null;
  vote_average: number | null;
  vote_count: number | null;
  registered: boolean;
  registered_item_id: string | null;
}

export interface TmdbSearchResponse {
  query: string;
  media_type: TmdbSearchMediaFilter;
  page: number;
  upstream_total_pages: number;
  upstream_total_results: number;
  returned_count: number;
  results: TmdbSearchResultItem[];
}

export interface TmdbDetailResponse {
  tmdb_id: number;
  media_type: TmdbMediaType;
  title: string;
  original_title: string | null;
  overview: string | null;
  tagline: string | null;
  original_language: string | null;
  adult: boolean | null;
  status: string | null;
  release_date: string | null;
  release_year: number | null;
  runtime_minutes: number | null;
  episode_runtime_minutes: number[] | null;
  first_air_date: string | null;
  last_air_date: string | null;
  number_of_seasons: number | null;
  number_of_episodes: number | null;
  genres: TmdbGenre[];
  poster_path: string | null;
  poster_url: string | null;
  backdrop_path: string | null;
  backdrop_url: string | null;
  popularity: number | null;
  vote_average: number | null;
  vote_count: number | null;
  cast: TmdbCastMember[];
  directors: TmdbCrewMember[];
  creators: TmdbCrewMember[];
  external_ids: TmdbExternalIds;
  registered: boolean;
  registered_item_id: string | null;
}

export interface ItemFromTmdbCreatePayload {
  media_type: TmdbMediaType;
  tmdb_id: number;
  category_id: string;
  collection_id?: string | null;
  status?: "PLANNED" | "COMPLETED";
  rating?: number;
  progress_note?: string | null;
  memo?: string | null;
  title?: string | null;
}

export interface TmdbAlreadyExistsDetail {
  code: "TMDB_ITEM_ALREADY_EXISTS";
  existing_item_id: string;
}
