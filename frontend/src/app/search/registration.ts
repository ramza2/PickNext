import type { TmdbMediaType, TmdbSearchResultItem } from "../../types/tmdb";
import type { SearchPageSnapshot } from "./types";

/** Patch only registration flags; preserve TMDB identity and display fields. */
export function patchSearchResultRegistered(
  rows: TmdbSearchResultItem[],
  mediaType: TmdbMediaType,
  tmdbId: number,
  registeredItemId: string,
): TmdbSearchResultItem[] {
  let changed = false;
  const next = rows.map((row) => {
    if (row.media_type !== mediaType || row.tmdb_id !== tmdbId) {
      return row;
    }
    if (row.registered && row.registered_item_id === registeredItemId) {
      return row;
    }
    changed = true;
    return {
      ...row,
      registered: true,
      registered_item_id: registeredItemId,
    };
  });
  return changed ? next : rows;
}

/** Clear registration flags for one TMDB identity; preserve display fields. */
export function patchSearchResultUnregistered(
  rows: TmdbSearchResultItem[],
  mediaType: TmdbMediaType,
  tmdbId: number,
): TmdbSearchResultItem[] {
  let changed = false;
  const next = rows.map((row) => {
    if (row.media_type !== mediaType || row.tmdb_id !== tmdbId) {
      return row;
    }
    if (!row.registered && row.registered_item_id == null) {
      return row;
    }
    changed = true;
    return {
      ...row,
      registered: false,
      registered_item_id: null,
    };
  });
  return changed ? next : rows;
}

export function shouldSyncRegistrationFromDetail(opts: {
  selectionRegistered: boolean;
  selectionItemId: string | null;
  detailRegistered: boolean;
  detailItemId: string | null;
}): boolean {
  if (!opts.detailRegistered || !opts.detailItemId) return false;
  if (
    opts.selectionRegistered
    && opts.selectionItemId === opts.detailItemId
  ) {
    return false;
  }
  return true;
}

export type DeletedItemExternalIdentity = {
  id: string;
  external_source?: string | null;
  external_media_type?: string | null;
  external_id?: string | null;
};

export function parseTmdbIdentityFromDeletedItem(
  deleted: DeletedItemExternalIdentity,
): { mediaType: TmdbMediaType; tmdbId: number } | null {
  if (deleted.external_source !== "tmdb") return null;
  const mediaType = deleted.external_media_type;
  if (mediaType !== "movie" && mediaType !== "tv") return null;
  if (deleted.external_id == null || deleted.external_id === "") return null;
  const tmdbId = Number(deleted.external_id);
  if (!Number.isFinite(tmdbId) || tmdbId < 1) return null;
  return { mediaType, tmdbId };
}

/** Apply unregistered patch to a search snapshot (no-op when unrelated). */
export function unmarkTmdbInSearchSnapshot(
  snapshot: SearchPageSnapshot | null,
  mediaType: TmdbMediaType,
  tmdbId: number,
): SearchPageSnapshot | null {
  if (!snapshot) return snapshot;
  const results = patchSearchResultUnregistered(
    snapshot.results,
    mediaType,
    tmdbId,
  );
  if (results === snapshot.results) return snapshot;
  return { ...snapshot, results };
}

export function unmarkDeletedItemInSearchSnapshot(
  snapshot: SearchPageSnapshot | null,
  deleted: DeletedItemExternalIdentity,
): SearchPageSnapshot | null {
  const identity = parseTmdbIdentityFromDeletedItem(deleted);
  if (!identity) return snapshot;
  return unmarkTmdbInSearchSnapshot(
    snapshot,
    identity.mediaType,
    identity.tmdbId,
  );
}
