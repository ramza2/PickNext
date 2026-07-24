import { useEffect, useRef, useState } from "react";
import { RefreshCw, X } from "lucide-react";
import { ApiError } from "../../api/client";
import { getTmdbDetails } from "../../api/tmdb";
import {
  tmdbDetailFailureMessage,
  tmdbErrorMessage,
} from "../../api/tmdbMessages";
import type {
  TmdbDetailResponse,
  TmdbMediaType,
  TmdbSearchResultItem,
} from "../../types/tmdb";
import { shouldSyncRegistrationFromDetail } from "./registration";

function isAbortError(err: unknown): boolean {
  if (err instanceof ApiError && err.status === 0 && err.message === "Request aborted") {
    return true;
  }
  return err instanceof Error && err.name === "AbortError";
}

export function TmdbDetailPanel({
  selection,
  onClose,
  onRegister,
  onOpenRegisteredItem,
  onRegistrationStateChange,
}: {
  selection: Pick<
    TmdbSearchResultItem,
    "tmdb_id" | "media_type" | "registered" | "registered_item_id" | "title"
  >;
  onClose: () => void;
  onRegister: (detail: TmdbDetailResponse) => void;
  onOpenRegisteredItem: (itemId: string) => void;
  onRegistrationStateChange: (
    mediaType: TmdbMediaType,
    tmdbId: number,
    registeredItemId: string,
  ) => void;
}) {
  const [detail, setDetail] = useState<TmdbDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const onRegistrationStateChangeRef = useRef(onRegistrationStateChange);
  onRegistrationStateChangeRef.current = onRegistrationStateChange;

  const selectionRegisteredRef = useRef(selection.registered);
  const selectionItemIdRef = useRef(selection.registered_item_id);
  selectionRegisteredRef.current = selection.registered;
  selectionItemIdRef.current = selection.registered_item_id;

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);
    setDetail(null);

    // Always fetch TMDB details by media_type + tmdb_id (never registered_item_id).
    void getTmdbDetails(selection.media_type, selection.tmdb_id, controller.signal)
      .then((payload) => {
        if (!active || controller.signal.aborted) return;
        setDetail(payload);
        if (
          shouldSyncRegistrationFromDetail({
            selectionRegistered: selectionRegisteredRef.current,
            selectionItemId: selectionItemIdRef.current,
            detailRegistered: payload.registered,
            detailItemId: payload.registered_item_id,
          })
          && payload.registered_item_id
        ) {
          onRegistrationStateChangeRef.current(
            payload.media_type,
            payload.tmdb_id,
            payload.registered_item_id,
          );
        }
      })
      .catch((err) => {
        if (!active || controller.signal.aborted || isAbortError(err)) return;
        setError(tmdbErrorMessage(err, tmdbDetailFailureMessage()));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [selection.media_type, selection.tmdb_id, reloadKey]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const registered = detail?.registered ?? selection.registered;
  const registeredItemId =
    detail?.registered_item_id ?? selection.registered_item_id;

  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex justify-end"
      role="dialog"
      aria-modal="true"
      aria-labelledby="tmdb-detail-title"
      onClick={onClose}
    >
      <div
        className="bg-card w-full sm:max-w-md h-full shadow-2xl overflow-y-auto"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="sticky top-0 bg-card border-b border-border px-4 py-3 flex items-center justify-between z-10">
          <h2 id="tmdb-detail-title" className="text-base font-bold text-foreground truncate pr-2">
            {detail?.title ?? selection.title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-xl text-muted-foreground hover:bg-muted"
            aria-label="닫기"
          >
            <X size={18} />
          </button>
        </div>

        <div className="p-4 space-y-4">
          {loading ? (
            <p className="text-sm text-muted-foreground py-8 text-center">불러오는 중...</p>
          ) : null}

          {!loading && error ? (
            <div className="text-center py-8">
              <p className="text-sm text-foreground mb-3">{error}</p>
              <div className="flex items-center justify-center gap-2">
                <button
                  type="button"
                  onClick={() => setReloadKey((value) => value + 1)}
                  className="inline-flex items-center gap-1.5 text-sm text-primary border border-primary/25 px-4 py-2 rounded-xl hover:bg-blue-50"
                >
                  <RefreshCw size={14} /> 다시 시도
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="inline-flex items-center gap-1.5 text-sm border border-border px-4 py-2 rounded-xl hover:bg-muted"
                >
                  닫기
                </button>
              </div>
            </div>
          ) : null}

          {!loading && !error && detail ? (
            <>
              <div className="flex gap-4">
                <div className="w-28 shrink-0 aspect-[2/3] rounded-xl overflow-hidden bg-muted border border-border">
                  {detail.poster_url ? (
                    <img
                      src={detail.poster_url}
                      alt=""
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-xs text-muted-foreground">
                      No Image
                    </div>
                  )}
                </div>
                <div className="min-w-0 flex-1 space-y-1.5">
                  <div className="flex flex-wrap gap-1.5">
                    <span className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-md bg-muted text-muted-foreground">
                      {detail.media_type}
                    </span>
                    {registered ? (
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700">
                        등록됨
                      </span>
                    ) : null}
                  </div>
                  {detail.original_title ? (
                    <p className="text-xs text-muted-foreground truncate">
                      {detail.original_title}
                    </p>
                  ) : null}
                  <p className="text-xs text-muted-foreground">
                    {[
                      detail.release_year,
                      detail.runtime_minutes
                        ? `${detail.runtime_minutes}분`
                        : null,
                      detail.number_of_seasons
                        ? `시즌 ${detail.number_of_seasons}`
                        : null,
                    ]
                      .filter(Boolean)
                      .join(" · ") || "—"}
                  </p>
                  {typeof detail.vote_average === "number" ? (
                    <p className="text-xs text-muted-foreground">
                      TMDB {detail.vote_average.toFixed(1)}
                      {typeof detail.vote_count === "number"
                        ? ` (${detail.vote_count})`
                        : ""}
                    </p>
                  ) : null}
                </div>
              </div>

              {detail.overview ? (
                <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
                  {detail.overview}
                </p>
              ) : null}

              {detail.genres.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {detail.genres.map((genre) => (
                    <span
                      key={genre.id}
                      className="text-xs px-2 py-1 rounded-lg bg-muted text-muted-foreground"
                    >
                      {genre.name}
                    </span>
                  ))}
                </div>
              ) : null}

              {detail.directors.length > 0 ? (
                <div>
                  <h3 className="text-xs font-semibold text-muted-foreground mb-1">감독</h3>
                  <p className="text-sm text-foreground">
                    {detail.directors.map((person) => person.name).join(", ")}
                  </p>
                </div>
              ) : null}

              {detail.creators.length > 0 ? (
                <div>
                  <h3 className="text-xs font-semibold text-muted-foreground mb-1">제작</h3>
                  <p className="text-sm text-foreground">
                    {detail.creators.map((person) => person.name).join(", ")}
                  </p>
                </div>
              ) : null}

              {detail.cast.length > 0 ? (
                <div>
                  <h3 className="text-xs font-semibold text-muted-foreground mb-2">출연</h3>
                  <ul className="space-y-1.5">
                    {detail.cast.map((person) => (
                      <li key={person.tmdb_person_id} className="text-sm text-foreground">
                        {person.name}
                        {person.character ? (
                          <span className="text-muted-foreground">
                            {" "}
                            · {person.character}
                          </span>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <p className="text-[11px] text-muted-foreground">
                이 제품은 TMDB API를 사용하지만, TMDB가 보증하거나 인증한 것은 아닙니다.
              </p>

              <div className="flex gap-2 pt-1">
                {registered && registeredItemId ? (
                  <button
                    type="button"
                    onClick={() => onOpenRegisteredItem(registeredItemId)}
                    className="flex-1 bg-primary hover:bg-blue-700 text-white py-2.5 rounded-xl text-sm font-medium"
                  >
                    기존 항목 보기
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => onRegister(detail)}
                    className="flex-1 bg-primary hover:bg-blue-700 text-white py-2.5 rounded-xl text-sm font-medium"
                  >
                    항목으로 등록
                  </button>
                )}
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
