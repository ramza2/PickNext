import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { ChevronLeft, ChevronRight, RefreshCw, Search } from "lucide-react";
import { ApiError } from "../../api/client";
import { getItem } from "../../api/catalog";
import { getTmdbStatus, searchTmdb } from "../../api/tmdb";
import {
  tmdbErrorMessage,
  tmdbNotConfiguredMessage,
  tmdbSearchFailureMessage,
  tmdbStatusUnavailableMessage,
} from "../../api/tmdbMessages";
import type { ApiItemDetail } from "../../types/api";
import type {
  TmdbDetailResponse,
  TmdbMediaType,
  TmdbSearchMediaFilter,
  TmdbSearchResultItem,
  TmdbStatusResponse,
} from "../../types/tmdb";
import { TmdbDetailPanel } from "./TmdbDetailPanel";
import { TmdbRegisterForm } from "./TmdbRegisterForm";
import {
  EMPTY_SEARCH_SNAPSHOT,
  type SearchPageSnapshot,
} from "./types";
import {
  patchSearchResultRegistered,
  patchSearchResultUnregistered,
} from "./registration";

const MEDIA_FILTERS: { value: TmdbSearchMediaFilter; label: string }[] = [
  { value: "all", label: "전체" },
  { value: "movie", label: "영화" },
  { value: "tv", label: "TV" },
];

const STALE_REGISTERED_ITEM_TOAST =
  "등록된 항목을 찾을 수 없어 검색 상태를 갱신했습니다.";
const SEARCH_REVALIDATE_FAIL_TOAST =
  "검색 결과의 등록 상태를 새로고치지 못했습니다. 표시 중인 결과는 이전 상태일 수 있습니다.";

function PosterThumb({
  url,
  title,
}: {
  url: string | null;
  title: string;
}) {
  return (
    <div className="w-16 sm:w-20 shrink-0 aspect-[2/3] rounded-lg overflow-hidden bg-muted border border-border">
      {url ? (
        <img
          src={url}
          alt=""
          className="w-full h-full object-cover"
          loading="lazy"
        />
      ) : (
        <div
          className="w-full h-full flex items-center justify-center text-[10px] text-muted-foreground px-1 text-center"
          title={title}
        >
          No Image
        </div>
      )}
    </div>
  );
}

export function SearchPage({
  showToast,
  openItemDetail,
  initialSnapshot,
  onSnapshotChange,
}: {
  showToast: (message: string) => void;
  openItemDetail: (itemId: string) => void;
  initialSnapshot?: SearchPageSnapshot | null;
  onSnapshotChange?: (snapshot: SearchPageSnapshot) => void;
}) {
  const [queryInput, setQueryInput] = useState(
    () => initialSnapshot?.queryInput ?? "",
  );
  const [appliedQuery, setAppliedQuery] = useState(
    () => initialSnapshot?.appliedQuery ?? "",
  );
  const [mediaType, setMediaType] = useState<TmdbSearchMediaFilter>(
    () => initialSnapshot?.mediaType ?? "all",
  );
  const [page, setPage] = useState(() => initialSnapshot?.page ?? 1);
  const [status, setStatus] = useState<TmdbStatusResponse | null>(
    () => initialSnapshot?.status ?? null,
  );
  const [statusLoading, setStatusLoading] = useState(!initialSnapshot?.status);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [results, setResults] = useState<TmdbSearchResultItem[]>(
    () => initialSnapshot?.results ?? [],
  );
  const [upstreamTotalPages, setUpstreamTotalPages] = useState(
    () => initialSnapshot?.upstreamTotalPages ?? 0,
  );
  const [upstreamTotalResults, setUpstreamTotalResults] = useState(
    () => initialSnapshot?.upstreamTotalResults ?? 0,
  );
  const [hasSearched, setHasSearched] = useState(
    () => initialSnapshot?.hasSearched ?? false,
  );
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [revalidating, setRevalidating] = useState(false);

  const [detailSelection, setDetailSelection] =
    useState<TmdbSearchResultItem | null>(null);
  const [registerDetail, setRegisterDetail] =
    useState<TmdbDetailResponse | null>(null);

  const onSnapshotChangeRef = useRef(onSnapshotChange);
  onSnapshotChangeRef.current = onSnapshotChange;
  const searchRequestIdRef = useRef(0);
  const statusRequestIdRef = useRef(0);
  const didRevalidateRef = useRef(false);

  const publishSnapshot = useCallback(
    (patch: Partial<SearchPageSnapshot>) => {
      const next: SearchPageSnapshot = {
        queryInput,
        appliedQuery,
        mediaType,
        page,
        status,
        results,
        upstreamTotalPages,
        upstreamTotalResults,
        hasSearched,
        ...patch,
      };
      onSnapshotChangeRef.current?.(next);
    },
    [
      queryInput,
      appliedQuery,
      mediaType,
      page,
      status,
      results,
      upstreamTotalPages,
      upstreamTotalResults,
      hasSearched,
    ],
  );

  const loadStatus = useCallback(async () => {
    const requestId = ++statusRequestIdRef.current;
    setStatusLoading(true);
    setStatusError(null);
    try {
      const payload = await getTmdbStatus();
      if (requestId !== statusRequestIdRef.current) return;
      setStatus(payload);
      publishSnapshot({ status: payload });
    } catch (err) {
      if (requestId !== statusRequestIdRef.current) return;
      setStatus(null);
      setStatusError(tmdbErrorMessage(err, tmdbStatusUnavailableMessage()));
    } finally {
      if (requestId === statusRequestIdRef.current) {
        setStatusLoading(false);
      }
    }
  }, [publishSnapshot]);

  useEffect(() => {
    if (!initialSnapshot?.status) {
      void loadStatus();
    }
  }, [initialSnapshot?.status, loadStatus]);

  const runSearch = useCallback(
    async (
      opts: {
        query: string;
        mediaType: TmdbSearchMediaFilter;
        page: number;
      },
      mode: "user" | "revalidate" = "user",
    ) => {
      const trimmed = opts.query.trim();
      if (!trimmed) {
        if (mode === "user") setSearchError("검색어를 입력해 주세요.");
        return;
      }
      if (status?.status === "NOT_CONFIGURED") {
        if (mode === "user") setSearchError(tmdbNotConfiguredMessage());
        return;
      }
      if (status?.status === "UNAVAILABLE") {
        if (mode === "user") setSearchError(tmdbStatusUnavailableMessage());
        return;
      }

      const requestId = ++searchRequestIdRef.current;
      if (mode === "user") {
        setSearchLoading(true);
        setSearchError(null);
      } else {
        setRevalidating(true);
      }
      try {
        const payload = await searchTmdb({
          query: trimmed,
          media_type: opts.mediaType,
          page: opts.page,
        });
        if (requestId !== searchRequestIdRef.current) return;
        setAppliedQuery(payload.query);
        setMediaType(payload.media_type);
        setPage(payload.page);
        setResults(payload.results);
        setUpstreamTotalPages(payload.upstream_total_pages);
        setUpstreamTotalResults(payload.upstream_total_results);
        setHasSearched(true);
        setQueryInput(payload.query);
        setSearchError(null);
        publishSnapshot({
          queryInput: payload.query,
          appliedQuery: payload.query,
          mediaType: payload.media_type,
          page: payload.page,
          results: payload.results,
          upstreamTotalPages: payload.upstream_total_pages,
          upstreamTotalResults: payload.upstream_total_results,
          hasSearched: true,
        });
      } catch (err) {
        if (requestId !== searchRequestIdRef.current) return;
        if (mode === "revalidate") {
          showToast(SEARCH_REVALIDATE_FAIL_TOAST);
        } else {
          setSearchError(tmdbErrorMessage(err, tmdbSearchFailureMessage()));
        }
      } finally {
        if (requestId === searchRequestIdRef.current) {
          setSearchLoading(false);
          setRevalidating(false);
        }
      }
    },
    [publishSnapshot, showToast, status?.status],
  );

  useEffect(() => {
    if (didRevalidateRef.current) return;
    if (!initialSnapshot?.hasSearched) return;
    const query = initialSnapshot.appliedQuery.trim();
    if (!query) return;
    if (status?.status !== "AVAILABLE") return;
    didRevalidateRef.current = true;
    void runSearch(
      {
        query,
        mediaType: initialSnapshot.mediaType,
        page: initialSnapshot.page,
      },
      "revalidate",
    );
  }, [initialSnapshot, runSearch, status?.status]);

  const onSubmitSearch = (event: FormEvent) => {
    event.preventDefault();
    void runSearch({ query: queryInput, mediaType, page: 1 }, "user");
  };

  const markRegistered = useCallback(
    (media: TmdbMediaType, tmdbId: number, itemId: string) => {
      setResults((prev) => {
        const next = patchSearchResultRegistered(prev, media, tmdbId, itemId);
        if (next === prev) return prev;
        publishSnapshot({ results: next });
        return next;
      });
      setDetailSelection((prev) => {
        if (
          !prev
          || prev.media_type !== media
          || prev.tmdb_id !== tmdbId
        ) {
          return prev;
        }
        if (prev.registered && prev.registered_item_id === itemId) {
          return prev;
        }
        return {
          ...prev,
          registered: true,
          registered_item_id: itemId,
        };
      });
    },
    [publishSnapshot],
  );

  const markUnregistered = useCallback(
    (media: TmdbMediaType, tmdbId: number) => {
      setResults((prev) => {
        const next = patchSearchResultUnregistered(prev, media, tmdbId);
        if (next === prev) return prev;
        publishSnapshot({ results: next });
        return next;
      });
      setDetailSelection((prev) => {
        if (
          !prev
          || prev.media_type !== media
          || prev.tmdb_id !== tmdbId
        ) {
          return prev;
        }
        if (!prev.registered && prev.registered_item_id == null) {
          return prev;
        }
        return {
          ...prev,
          registered: false,
          registered_item_id: null,
        };
      });
    },
    [publishSnapshot],
  );

  const openRegisteredItem = useCallback(
    async (row: Pick<
      TmdbSearchResultItem,
      "media_type" | "tmdb_id" | "registered_item_id"
    >) => {
      const itemId = row.registered_item_id;
      if (!itemId) return;
      try {
        await getItem(itemId);
        openItemDetail(itemId);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          markUnregistered(row.media_type, row.tmdb_id);
          showToast(STALE_REGISTERED_ITEM_TOAST);
          return;
        }
        showToast(
          tmdbErrorMessage(err, "항목을 열지 못했습니다. 잠시 후 다시 시도해 주세요."),
        );
      }
    },
    [markUnregistered, openItemDetail, showToast],
  );

  const handleRegistered = (item: ApiItemDetail) => {
    if (registerDetail) {
      markRegistered(
        registerDetail.media_type,
        registerDetail.tmdb_id,
        item.id,
      );
    }
    setRegisterDetail(null);
    setDetailSelection(null);
    openItemDetail(item.id);
  };

  const handleAlreadyExists = (itemId: string) => {
    if (registerDetail) {
      markRegistered(registerDetail.media_type, registerDetail.tmdb_id, itemId);
    }
    setRegisterDetail(null);
    setDetailSelection(null);
    openItemDetail(itemId);
  };

  const canSearch =
    !statusLoading
    && status?.status === "AVAILABLE"
    && !searchLoading;

  const hasNext = page < upstreamTotalPages;

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6">
      <h1 className="text-xl font-bold text-foreground mb-5">영화·드라마 검색</h1>

      {statusLoading ? (
        <div className="bg-card border border-border rounded-2xl p-6 text-center text-sm text-muted-foreground mb-4">
          TMDB 연결 상태 확인 중...
        </div>
      ) : null}

      {!statusLoading && statusError ? (
        <div className="bg-card border border-border rounded-2xl p-6 text-center mb-4">
          <p className="text-sm text-foreground mb-3">{statusError}</p>
          <button
            type="button"
            onClick={() => void loadStatus()}
            className="inline-flex items-center gap-1.5 text-sm text-primary border border-primary/25 px-4 py-2 rounded-xl hover:bg-blue-50"
          >
            <RefreshCw size={14} /> 다시 시도
          </button>
        </div>
      ) : null}

      {!statusLoading && status?.status === "NOT_CONFIGURED" ? (
        <div className="bg-card border border-border rounded-2xl p-6 text-center mb-4">
          <p className="text-sm font-medium text-foreground mb-1">TMDB 미설정</p>
          <p className="text-sm text-muted-foreground">{tmdbNotConfiguredMessage()}</p>
        </div>
      ) : null}

      {!statusLoading && status?.status === "UNAVAILABLE" ? (
        <div className="bg-card border border-border rounded-2xl p-6 text-center mb-4">
          <p className="text-sm font-medium text-foreground mb-1">TMDB 사용 불가</p>
          <p className="text-sm text-muted-foreground mb-3">
            {tmdbStatusUnavailableMessage()}
          </p>
          <button
            type="button"
            onClick={() => void loadStatus()}
            className="inline-flex items-center gap-1.5 text-sm text-primary border border-primary/25 px-4 py-2 rounded-xl hover:bg-blue-50"
          >
            <RefreshCw size={14} /> 다시 시도
          </button>
        </div>
      ) : null}

      <form onSubmit={onSubmitSearch} className="space-y-3 mb-5">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            />
            <input
              value={queryInput}
              onChange={(event) => {
                const next = event.target.value;
                setQueryInput(next);
                publishSnapshot({ queryInput: next });
              }}
              placeholder="영화·드라마 제목 검색"
              className="w-full border border-border rounded-xl pl-9 pr-3 py-2.5 text-sm bg-card"
              disabled={status?.status === "NOT_CONFIGURED"}
            />
          </div>
          <button
            type="submit"
            disabled={!canSearch}
            className="px-4 py-2.5 rounded-xl bg-primary text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {searchLoading ? "검색 중..." : "검색"}
          </button>
        </div>
        <div className="flex gap-2">
          {MEDIA_FILTERS.map((filter) => (
            <button
              key={filter.value}
              type="button"
              disabled={searchLoading}
              onClick={() => {
                setMediaType(filter.value);
                publishSnapshot({ mediaType: filter.value });
                if (hasSearched && appliedQuery) {
                  void runSearch({
                    query: appliedQuery,
                    mediaType: filter.value,
                    page: 1,
                  }, "user");
                }
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                mediaType === filter.value
                  ? "border-primary bg-blue-50 text-primary"
                  : "border-border text-muted-foreground hover:bg-muted"
              }`}
            >
              {filter.label}
            </button>
          ))}
        </div>
      </form>

      {revalidating ? (
        <p className="text-xs text-muted-foreground mb-3">등록 상태 확인 중...</p>
      ) : null}

      {searchError ? (
        <div className="bg-card border border-border rounded-2xl p-6 text-center mb-4">
          <p className="text-sm text-foreground mb-3">{searchError}</p>
          {appliedQuery ? (
            <button
              type="button"
              onClick={() =>
                void runSearch({ query: appliedQuery, mediaType, page }, "user")
              }
              className="inline-flex items-center gap-1.5 text-sm text-primary border border-primary/25 px-4 py-2 rounded-xl hover:bg-blue-50"
            >
              <RefreshCw size={14} /> 다시 시도
            </button>
          ) : null}
        </div>
      ) : null}

      {hasSearched && !searchError ? (
        <div className="mb-3 flex items-center justify-between gap-2">
          <p className="text-xs text-muted-foreground">
            &ldquo;{appliedQuery}&rdquo; · {upstreamTotalResults.toLocaleString()}건
            {upstreamTotalPages > 0
              ? ` · ${page}/${upstreamTotalPages}페이지`
              : ""}
          </p>
        </div>
      ) : null}

      {searchLoading && results.length === 0 ? (
        <div className="bg-card border border-border rounded-2xl p-8 text-center text-sm text-muted-foreground">
          검색 중...
        </div>
      ) : null}

      {!searchLoading && hasSearched && !searchError && results.length === 0 ? (
        <div className="bg-card border border-border rounded-2xl p-8 text-center">
          <p className="text-sm font-medium text-foreground mb-1">검색 결과가 없습니다</p>
          <p className="text-sm text-muted-foreground">다른 검색어나 유형으로 다시 시도해 보세요.</p>
        </div>
      ) : null}

      {results.length > 0 ? (
        <ul className="space-y-3">
          {results.map((row) => (
            <li
              key={`${row.media_type}-${row.tmdb_id}`}
              className="bg-card border border-border rounded-2xl p-3 sm:p-4 flex gap-3"
            >
              <PosterThumb url={row.poster_url} title={row.title} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-1.5 mb-1">
                  <span className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-md bg-muted text-muted-foreground">
                    {row.media_type}
                  </span>
                  {row.registered ? (
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700">
                      등록됨
                    </span>
                  ) : null}
                </div>
                <h2 className="text-sm font-semibold text-foreground truncate">
                  {row.title}
                </h2>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {[row.release_year, row.original_title]
                    .filter(Boolean)
                    .join(" · ") || "—"}
                </p>
                <div className="flex flex-wrap gap-2 mt-3">
                  <button
                    type="button"
                    onClick={() => setDetailSelection(row)}
                    className="text-xs text-primary border border-primary/25 px-3 py-1.5 rounded-lg hover:bg-blue-50"
                  >
                    상세보기
                  </button>
                  {row.registered && row.registered_item_id ? (
                    <button
                      type="button"
                      onClick={() => void openRegisteredItem(row)}
                      className="text-xs border border-border px-3 py-1.5 rounded-lg hover:bg-muted"
                    >
                      기존 항목 보기
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setDetailSelection(row)}
                      className="text-xs bg-primary text-white px-3 py-1.5 rounded-lg hover:bg-blue-700"
                    >
                      등록
                    </button>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      {hasSearched && upstreamTotalPages > 1 ? (
        <div className="flex items-center justify-center gap-3 mt-5">
          <button
            type="button"
            disabled={page <= 1 || searchLoading}
            onClick={() =>
              void runSearch({
                query: appliedQuery,
                mediaType,
                page: page - 1,
              }, "user")
            }
            className="inline-flex items-center gap-1 text-sm border border-border px-3 py-2 rounded-xl disabled:opacity-40"
          >
            <ChevronLeft size={16} /> 이전
          </button>
          <span className="text-xs text-muted-foreground">
            {page} / {upstreamTotalPages}
          </span>
          <button
            type="button"
            disabled={!hasNext || searchLoading}
            onClick={() =>
              void runSearch({
                query: appliedQuery,
                mediaType,
                page: page + 1,
              }, "user")
            }
            className="inline-flex items-center gap-1 text-sm border border-border px-3 py-2 rounded-xl disabled:opacity-40"
          >
            다음 <ChevronRight size={16} />
          </button>
        </div>
      ) : null}

      <p className="text-[11px] text-muted-foreground mt-6 leading-relaxed">
        이 제품은 TMDB API를 사용하지만, TMDB가 보증하거나 인증한 것은 아닙니다.
        This product uses the TMDB API but is not endorsed or certified by TMDB.
      </p>

      {detailSelection ? (
        <TmdbDetailPanel
          selection={detailSelection}
          onClose={() => setDetailSelection(null)}
          onRegister={(detail) => setRegisterDetail(detail)}
          onOpenRegisteredItem={(itemId) => {
            setDetailSelection(null);
            void openRegisteredItem({
              media_type: detailSelection.media_type,
              tmdb_id: detailSelection.tmdb_id,
              registered_item_id: itemId,
            });
          }}
          onRegistrationStateChange={markRegistered}
        />
      ) : null}

      {registerDetail ? (
        <TmdbRegisterForm
          detail={registerDetail}
          mediaType={registerDetail.media_type}
          tmdbId={registerDetail.tmdb_id}
          onClose={() => setRegisterDetail(null)}
          onRegistered={handleRegistered}
          onAlreadyExists={handleAlreadyExists}
          showToast={showToast}
        />
      ) : null}
    </div>
  );
}

export { EMPTY_SEARCH_SNAPSHOT };
export type { SearchPageSnapshot };
