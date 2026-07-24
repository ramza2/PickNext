"""TMDB service: normalize responses, image URLs, registration lookup."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.integrations.tmdb.client import TmdbClient
from app.integrations.tmdb.errors import TmdbError, TmdbNotConfiguredError
from app.models import Item, User
from app.schemas.tmdb import (
    TmdbCastMember,
    TmdbCrewMember,
    TmdbDetailResponse,
    TmdbExternalIds,
    TmdbGenre,
    TmdbSearchMediaFilter,
    TmdbSearchResponse,
    TmdbSearchResultItem,
    TmdbStatusResponse,
)

EXTERNAL_SOURCE_TMDB = "tmdb"
CAST_LIMIT = 10
MAX_QUERY_LENGTH = 200


def trim_search_query(raw: str) -> str:
    return raw.strip()


def parse_tmdb_date(value: object) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def year_from_date(value: date | None) -> int | None:
    return value.year if value is not None else None


class TmdbService:
    def __init__(self, settings: Settings, client: TmdbClient) -> None:
        self._settings = settings
        self._client = client

    async def status(self) -> TmdbStatusResponse:
        payload = await self._client.probe_status()
        return TmdbStatusResponse(**payload)

    def _secure_base_url(self, configuration: dict[str, Any]) -> str | None:
        images = configuration.get("images")
        if not isinstance(images, dict):
            return None
        base = images.get("secure_base_url") or images.get("base_url")
        if not isinstance(base, str) or not base.strip():
            return None
        return base if base.endswith("/") else f"{base}/"

    def _pick_size(self, available: object, preferred: str) -> str:
        if isinstance(available, list):
            sizes = [str(item) for item in available]
            if preferred in sizes:
                return preferred
            # Prefer last non-original size when preferred missing.
            candidates = [s for s in sizes if s != "original"]
            if candidates:
                return candidates[-1]
            if sizes:
                return sizes[0]
        return preferred

    def build_image_url(
        self,
        configuration: dict[str, Any],
        *,
        file_path: str | None,
        kind: str,
    ) -> str | None:
        if not file_path or not isinstance(file_path, str):
            return None
        path = file_path.strip()
        if not path:
            return None
        if not path.startswith("/"):
            path = f"/{path}"

        base = self._secure_base_url(configuration)
        if base is None:
            return None

        images = configuration.get("images")
        if not isinstance(images, dict):
            images = {}

        if kind == "poster":
            size = self._pick_size(
                images.get("poster_sizes"),
                self._settings.tmdb_poster_size,
            )
        elif kind == "backdrop":
            size = self._pick_size(
                images.get("backdrop_sizes"),
                self._settings.tmdb_backdrop_size,
            )
        else:
            size = self._pick_size(
                images.get("profile_sizes"),
                self._settings.tmdb_profile_size,
            )
        return f"{base}{size}{path}"

    def _registered_map(
        self,
        db: Session,
        user: User,
        pairs: list[tuple[str, str]],
    ) -> dict[tuple[str, str], UUID]:
        if not pairs:
            return {}
        media_types = {media for media, _ in pairs}
        external_ids = {ext_id for _, ext_id in pairs}
        rows = db.scalars(
            select(Item).where(
                Item.user_id == user.id,
                Item.external_source == EXTERNAL_SOURCE_TMDB,
                Item.external_media_type.in_(media_types),
                Item.external_id.in_(external_ids),
            )
        ).all()
        mapping: dict[tuple[str, str], UUID] = {}
        wanted = set(pairs)
        for item in rows:
            if item.external_media_type is None or item.external_id is None:
                continue
            key = (item.external_media_type, item.external_id)
            if key in wanted:
                mapping[key] = item.id
        return mapping

    def _normalize_search_row(
        self,
        raw: dict[str, Any],
        *,
        forced_media_type: str | None,
        configuration: dict[str, Any],
        registered_map: dict[tuple[str, str], UUID],
    ) -> TmdbSearchResultItem | None:
        media_type = forced_media_type or raw.get("media_type")
        if media_type not in ("movie", "tv"):
            return None
        tmdb_id = raw.get("id")
        if not isinstance(tmdb_id, int):
            return None

        if media_type == "movie":
            title = raw.get("title")
            original_title = raw.get("original_title")
            release = parse_tmdb_date(raw.get("release_date"))
        else:
            title = raw.get("name")
            original_title = raw.get("original_name")
            release = parse_tmdb_date(raw.get("first_air_date"))

        if not isinstance(title, str) or not title.strip():
            title = original_title if isinstance(original_title, str) else None
        if not isinstance(title, str) or not title.strip():
            return None

        poster_path = raw.get("poster_path")
        backdrop_path = raw.get("backdrop_path")
        if not isinstance(poster_path, str):
            poster_path = None
        if not isinstance(backdrop_path, str):
            backdrop_path = None

        external_id = str(tmdb_id)
        reg_id = registered_map.get((media_type, external_id))

        genre_ids_raw = raw.get("genre_ids") or []
        genre_ids = [g for g in genre_ids_raw if isinstance(g, int)] if isinstance(
            genre_ids_raw, list
        ) else []

        return TmdbSearchResultItem(
            tmdb_id=tmdb_id,
            media_type=media_type,  # type: ignore[arg-type]
            title=title.strip(),
            original_title=(
                original_title.strip()
                if isinstance(original_title, str) and original_title.strip()
                else None
            ),
            overview=raw.get("overview") if isinstance(raw.get("overview"), str) else None,
            original_language=(
                raw.get("original_language")
                if isinstance(raw.get("original_language"), str)
                else None
            ),
            release_date=release,
            release_year=year_from_date(release),
            genre_ids=genre_ids,
            poster_path=poster_path,
            poster_url=self.build_image_url(
                configuration, file_path=poster_path, kind="poster"
            ),
            backdrop_path=backdrop_path,
            backdrop_url=self.build_image_url(
                configuration, file_path=backdrop_path, kind="backdrop"
            ),
            adult=raw.get("adult") if isinstance(raw.get("adult"), bool) else None,
            popularity=(
                float(raw["popularity"])
                if isinstance(raw.get("popularity"), (int, float))
                else None
            ),
            vote_average=(
                float(raw["vote_average"])
                if isinstance(raw.get("vote_average"), (int, float))
                else None
            ),
            vote_count=(
                int(raw["vote_count"])
                if isinstance(raw.get("vote_count"), int)
                else None
            ),
            registered=reg_id is not None,
            registered_item_id=reg_id,
        )

    async def search(
        self,
        *,
        db: Session,
        user: User,
        query: str,
        media_type: TmdbSearchMediaFilter,
        page: int,
    ) -> TmdbSearchResponse:
        if self._client.auth_mode == "none":
            raise TmdbNotConfiguredError()

        if media_type == "movie":
            upstream = await self._client.search_movie(query=query, page=page)
            forced: str | None = "movie"
        elif media_type == "tv":
            upstream = await self._client.search_tv(query=query, page=page)
            forced = "tv"
        else:
            upstream = await self._client.search_multi(query=query, page=page)
            forced = None

        configuration = await self._client.get_configuration()
        raw_results = upstream.get("results")
        if not isinstance(raw_results, list):
            raw_results = []

        pairs: list[tuple[str, str]] = []
        for raw in raw_results:
            if not isinstance(raw, dict):
                continue
            mt = forced or raw.get("media_type")
            tid = raw.get("id")
            if mt in ("movie", "tv") and isinstance(tid, int):
                pairs.append((mt, str(tid)))

        registered_map = self._registered_map(db, user, pairs)

        normalized: list[TmdbSearchResultItem] = []
        for raw in raw_results:
            if not isinstance(raw, dict):
                continue
            item = self._normalize_search_row(
                raw,
                forced_media_type=forced,
                configuration=configuration,
                registered_map=registered_map,
            )
            if item is not None:
                normalized.append(item)

        total_pages = upstream.get("total_pages")
        total_results = upstream.get("total_results")
        return TmdbSearchResponse(
            query=query,
            media_type=media_type,
            page=page,
            upstream_total_pages=int(total_pages) if isinstance(total_pages, int) else 0,
            upstream_total_results=(
                int(total_results) if isinstance(total_results, int) else 0
            ),
            returned_count=len(normalized),
            results=normalized,
        )

    def _map_cast(
        self,
        credits: dict[str, Any],
        configuration: dict[str, Any],
    ) -> list[TmdbCastMember]:
        cast_raw = credits.get("cast")
        if not isinstance(cast_raw, list):
            return []
        ordered = sorted(
            [c for c in cast_raw if isinstance(c, dict)],
            key=lambda c: c.get("order") if isinstance(c.get("order"), int) else 10_000,
        )[:CAST_LIMIT]
        result: list[TmdbCastMember] = []
        for row in ordered:
            person_id = row.get("id")
            name = row.get("name")
            if not isinstance(person_id, int) or not isinstance(name, str):
                continue
            profile_path = row.get("profile_path")
            if not isinstance(profile_path, str):
                profile_path = None
            result.append(
                TmdbCastMember(
                    tmdb_person_id=person_id,
                    name=name,
                    character=(
                        row.get("character")
                        if isinstance(row.get("character"), str)
                        else None
                    ),
                    profile_path=profile_path,
                    profile_url=self.build_image_url(
                        configuration, file_path=profile_path, kind="profile"
                    ),
                    order=row.get("order") if isinstance(row.get("order"), int) else None,
                )
            )
        return result

    def _map_directors(
        self,
        credits: dict[str, Any],
        configuration: dict[str, Any],
    ) -> list[TmdbCrewMember]:
        crew_raw = credits.get("crew")
        if not isinstance(crew_raw, list):
            return []
        result: list[TmdbCrewMember] = []
        for row in crew_raw:
            if not isinstance(row, dict):
                continue
            if row.get("job") != "Director":
                continue
            person_id = row.get("id")
            name = row.get("name")
            if not isinstance(person_id, int) or not isinstance(name, str):
                continue
            profile_path = row.get("profile_path")
            if not isinstance(profile_path, str):
                profile_path = None
            result.append(
                TmdbCrewMember(
                    tmdb_person_id=person_id,
                    name=name,
                    job="Director",
                    profile_path=profile_path,
                    profile_url=self.build_image_url(
                        configuration, file_path=profile_path, kind="profile"
                    ),
                )
            )
        return result

    def _map_creators(
        self,
        created_by: object,
        configuration: dict[str, Any],
    ) -> list[TmdbCrewMember]:
        if not isinstance(created_by, list):
            return []
        result: list[TmdbCrewMember] = []
        for row in created_by:
            if not isinstance(row, dict):
                continue
            person_id = row.get("id")
            name = row.get("name")
            if not isinstance(person_id, int) or not isinstance(name, str):
                continue
            profile_path = row.get("profile_path")
            if not isinstance(profile_path, str):
                profile_path = None
            result.append(
                TmdbCrewMember(
                    tmdb_person_id=person_id,
                    name=name,
                    job="Creator",
                    profile_path=profile_path,
                    profile_url=self.build_image_url(
                        configuration, file_path=profile_path, kind="profile"
                    ),
                )
            )
        return result

    def _map_external_ids(self, raw: object) -> TmdbExternalIds:
        if not isinstance(raw, dict):
            return TmdbExternalIds()

        def pick(key: str) -> str | None:
            value = raw.get(key)
            return value if isinstance(value, str) and value.strip() else None

        return TmdbExternalIds(
            imdb_id=pick("imdb_id"),
            wikidata_id=pick("wikidata_id"),
            facebook_id=pick("facebook_id"),
            instagram_id=pick("instagram_id"),
            twitter_id=pick("twitter_id"),
        )

    async def details(
        self,
        *,
        db: Session,
        user: User,
        media_type: str,
        tmdb_id: int,
    ) -> TmdbDetailResponse:
        if self._client.auth_mode == "none":
            raise TmdbNotConfiguredError()
        if media_type == "movie":
            raw = await self._client.movie_details(tmdb_id)
        elif media_type == "tv":
            raw = await self._client.tv_details(tmdb_id)
        else:
            raise ValueError("unsupported media_type")

        configuration = await self._client.get_configuration()
        registered_map = self._registered_map(
            db, user, [(media_type, str(tmdb_id))]
        )
        reg_id = registered_map.get((media_type, str(tmdb_id)))

        credits = raw.get("credits") if isinstance(raw.get("credits"), dict) else {}
        external_ids_raw = raw.get("external_ids")

        if media_type == "movie":
            title = raw.get("title")
            original_title = raw.get("original_title")
            release = parse_tmdb_date(raw.get("release_date"))
            first_air = None
            last_air = None
            runtime = raw.get("runtime") if isinstance(raw.get("runtime"), int) else None
            episode_runtime = None
            seasons = None
            episodes = None
            creators: list[TmdbCrewMember] = []
            directors = self._map_directors(credits, configuration)
        else:
            title = raw.get("name")
            original_title = raw.get("original_name")
            first_air = parse_tmdb_date(raw.get("first_air_date"))
            last_air = parse_tmdb_date(raw.get("last_air_date"))
            release = first_air
            runtime = None
            ep_rt = raw.get("episode_run_time")
            episode_runtime = (
                [int(x) for x in ep_rt if isinstance(x, int)]
                if isinstance(ep_rt, list)
                else None
            )
            seasons = (
                raw.get("number_of_seasons")
                if isinstance(raw.get("number_of_seasons"), int)
                else None
            )
            episodes = (
                raw.get("number_of_episodes")
                if isinstance(raw.get("number_of_episodes"), int)
                else None
            )
            creators = self._map_creators(raw.get("created_by"), configuration)
            directors = []

        if not isinstance(title, str) or not title.strip():
            title = original_title if isinstance(original_title, str) else "Untitled"

        genres_raw = raw.get("genres")
        genres: list[TmdbGenre] = []
        if isinstance(genres_raw, list):
            for g in genres_raw:
                if isinstance(g, dict) and isinstance(g.get("id"), int) and isinstance(
                    g.get("name"), str
                ):
                    genres.append(TmdbGenre(id=g["id"], name=g["name"]))

        poster_path = raw.get("poster_path") if isinstance(raw.get("poster_path"), str) else None
        backdrop_path = (
            raw.get("backdrop_path") if isinstance(raw.get("backdrop_path"), str) else None
        )

        return TmdbDetailResponse(
            tmdb_id=tmdb_id,
            media_type=media_type,  # type: ignore[arg-type]
            title=title.strip(),
            original_title=(
                original_title.strip()
                if isinstance(original_title, str) and original_title.strip()
                else None
            ),
            overview=raw.get("overview") if isinstance(raw.get("overview"), str) else None,
            tagline=raw.get("tagline") if isinstance(raw.get("tagline"), str) else None,
            original_language=(
                raw.get("original_language")
                if isinstance(raw.get("original_language"), str)
                else None
            ),
            adult=raw.get("adult") if isinstance(raw.get("adult"), bool) else None,
            status=raw.get("status") if isinstance(raw.get("status"), str) else None,
            release_date=release,
            release_year=year_from_date(release),
            runtime_minutes=runtime,
            episode_runtime_minutes=episode_runtime,
            first_air_date=first_air,
            last_air_date=last_air,
            number_of_seasons=seasons,
            number_of_episodes=episodes,
            genres=genres,
            poster_path=poster_path,
            poster_url=self.build_image_url(
                configuration, file_path=poster_path, kind="poster"
            ),
            backdrop_path=backdrop_path,
            backdrop_url=self.build_image_url(
                configuration, file_path=backdrop_path, kind="backdrop"
            ),
            popularity=(
                float(raw["popularity"])
                if isinstance(raw.get("popularity"), (int, float))
                else None
            ),
            vote_average=(
                float(raw["vote_average"])
                if isinstance(raw.get("vote_average"), (int, float))
                else None
            ),
            vote_count=(
                int(raw["vote_count"]) if isinstance(raw.get("vote_count"), int) else None
            ),
            cast=self._map_cast(credits, configuration),
            directors=directors,
            creators=creators,
            external_ids=self._map_external_ids(external_ids_raw),
            registered=reg_id is not None,
            registered_item_id=reg_id,
        )
