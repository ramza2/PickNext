"""TMDB API response schemas."""

from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

TmdbMediaType = Literal["movie", "tv"]
TmdbSearchMediaFilter = Literal["all", "movie", "tv"]
TmdbStatusValue = Literal["AVAILABLE", "NOT_CONFIGURED", "UNAVAILABLE"]
TmdbAuthMode = Literal["bearer", "api_key", "none"]


class TmdbStatusResponse(BaseModel):
    status: TmdbStatusValue
    configured: bool
    available: bool
    auth_mode: TmdbAuthMode
    language: str
    region: str
    checked_at: str


class TmdbGenre(BaseModel):
    id: int
    name: str


class TmdbCastMember(BaseModel):
    tmdb_person_id: int
    name: str
    character: str | None = None
    profile_path: str | None = None
    profile_url: str | None = None
    order: int | None = None


class TmdbCrewMember(BaseModel):
    tmdb_person_id: int
    name: str
    job: str | None = None
    profile_path: str | None = None
    profile_url: str | None = None


class TmdbExternalIds(BaseModel):
    imdb_id: str | None = None
    wikidata_id: str | None = None
    facebook_id: str | None = None
    instagram_id: str | None = None
    twitter_id: str | None = None


class TmdbSearchResultItem(BaseModel):
    tmdb_id: int
    media_type: TmdbMediaType
    title: str
    original_title: str | None = None
    overview: str | None = None
    original_language: str | None = None
    release_date: date | None = None
    release_year: int | None = None
    genre_ids: list[int] = Field(default_factory=list)
    poster_path: str | None = None
    poster_url: str | None = None
    backdrop_path: str | None = None
    backdrop_url: str | None = None
    adult: bool | None = None
    popularity: float | None = None
    vote_average: float | None = None
    vote_count: int | None = None
    registered: bool = False
    registered_item_id: UUID | None = None


class TmdbSearchResponse(BaseModel):
    query: str
    media_type: TmdbSearchMediaFilter
    page: int
    upstream_total_pages: int
    upstream_total_results: int
    returned_count: int
    results: list[TmdbSearchResultItem]


class TmdbDetailResponse(BaseModel):
    tmdb_id: int
    media_type: TmdbMediaType
    title: str
    original_title: str | None = None
    overview: str | None = None
    tagline: str | None = None
    original_language: str | None = None
    adult: bool | None = None
    status: str | None = None
    release_date: date | None = None
    release_year: int | None = None
    runtime_minutes: int | None = None
    episode_runtime_minutes: list[int] | None = None
    first_air_date: date | None = None
    last_air_date: date | None = None
    number_of_seasons: int | None = None
    number_of_episodes: int | None = None
    genres: list[TmdbGenre] = Field(default_factory=list)
    poster_path: str | None = None
    poster_url: str | None = None
    backdrop_path: str | None = None
    backdrop_url: str | None = None
    popularity: float | None = None
    vote_average: float | None = None
    vote_count: int | None = None
    cast: list[TmdbCastMember] = Field(default_factory=list)
    directors: list[TmdbCrewMember] = Field(default_factory=list)
    creators: list[TmdbCrewMember] = Field(default_factory=list)
    external_ids: TmdbExternalIds = Field(default_factory=TmdbExternalIds)
    registered: bool = False
    registered_item_id: UUID | None = None
