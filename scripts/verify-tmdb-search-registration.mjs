/**
 * Regression checks for TMDB search registration patch helpers.
 * Mirrors frontend/src/app/search/registration.ts (keep in sync).
 *
 * Run: node scripts/verify-tmdb-search-registration.mjs
 */

function patchSearchResultRegistered(rows, mediaType, tmdbId, registeredItemId) {
  let changed = false;
  const next = rows.map((row) => {
    if (row.media_type !== mediaType || row.tmdb_id !== tmdbId) return row;
    if (row.registered && row.registered_item_id === registeredItemId) return row;
    changed = true;
    return {
      ...row,
      registered: true,
      registered_item_id: registeredItemId,
    };
  });
  return changed ? next : rows;
}

function patchSearchResultUnregistered(rows, mediaType, tmdbId) {
  let changed = false;
  const next = rows.map((row) => {
    if (row.media_type !== mediaType || row.tmdb_id !== tmdbId) return row;
    if (!row.registered && row.registered_item_id == null) return row;
    changed = true;
    return {
      ...row,
      registered: false,
      registered_item_id: null,
    };
  });
  return changed ? next : rows;
}

function shouldSyncRegistrationFromDetail(opts) {
  if (!opts.detailRegistered || !opts.detailItemId) return false;
  if (
    opts.selectionRegistered
    && opts.selectionItemId === opts.detailItemId
  ) {
    return false;
  }
  return true;
}

function parseTmdbIdentityFromDeletedItem(deleted) {
  if (deleted.external_source !== "tmdb") return null;
  const mediaType = deleted.external_media_type;
  if (mediaType !== "movie" && mediaType !== "tv") return null;
  if (deleted.external_id == null || deleted.external_id === "") return null;
  const tmdbId = Number(deleted.external_id);
  if (!Number.isFinite(tmdbId) || tmdbId < 1) return null;
  return { mediaType, tmdbId };
}

function unmarkDeletedItemInSearchSnapshot(snapshot, deleted) {
  const identity = parseTmdbIdentityFromDeletedItem(deleted);
  if (!identity || !snapshot) return snapshot;
  const results = patchSearchResultUnregistered(
    snapshot.results,
    identity.mediaType,
    identity.tmdbId,
  );
  if (results === snapshot.results) return snapshot;
  return { ...snapshot, results };
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

const itemId = "11111111-1111-1111-1111-111111111111";
const base = {
  tmdb_id: 872585,
  media_type: "movie",
  title: "오펜하이머",
  original_title: "Oppenheimer",
  overview: null,
  original_language: "en",
  release_date: "2023-07-19",
  release_year: 2023,
  genre_ids: [],
  poster_path: "/p.jpg",
  poster_url: "https://image.tmdb.org/t/p/w500/p.jpg",
  backdrop_path: null,
  backdrop_url: null,
  adult: false,
  popularity: 1,
  vote_average: 8,
  vote_count: 10,
  registered: false,
  registered_item_id: null,
};

const rows = [base, { ...base, tmdb_id: 1, title: "Other" }];
const patched = patchSearchResultRegistered(rows, "movie", 872585, itemId);
assert(patched !== rows, "registered patch should create new array");
assert(patched[0].registered === true, "target registered");
assert(patched[0].registered_item_id === itemId, "target item id");
assert(patched[0].tmdb_id === 872585, "tmdb_id preserved");
assert(patched[0].media_type === "movie", "media_type preserved");
assert(patched[0].title === "오펜하이머", "title preserved");
assert(patched[0].poster_url === base.poster_url, "poster_url preserved");
assert(patched[1].registered === false, "other row untouched");

const again = patchSearchResultRegistered(patched, "movie", 872585, itemId);
assert(again === patched, "idempotent patch returns same array");

assert(
  shouldSyncRegistrationFromDetail({
    selectionRegistered: false,
    selectionItemId: null,
    detailRegistered: true,
    detailItemId: itemId,
  }) === true,
  "unregistered selection should sync from detail",
);

assert(
  shouldSyncRegistrationFromDetail({
    selectionRegistered: true,
    selectionItemId: itemId,
    detailRegistered: true,
    detailItemId: itemId,
  }) === false,
  "already-synced registered selection must not re-notify (avoids detail loading loop)",
);

assert(
  shouldSyncRegistrationFromDetail({
    selectionRegistered: true,
    selectionItemId: itemId,
    detailRegistered: false,
    detailItemId: null,
  }) === false,
  "unregistered detail must not sync",
);

const afterDelete = patchSearchResultUnregistered(patched, "movie", 872585);
assert(afterDelete[0].registered === false, "unregistered clears badge flag");
assert(afterDelete[0].registered_item_id === null, "unregistered clears item id");
assert(afterDelete[0].tmdb_id === 872585, "unregistered keeps tmdb_id");
assert(afterDelete[0].title === "오펜하이머", "unregistered keeps title");
assert(afterDelete[1].registered === false, "sibling untouched");

const sameIdTv = patchSearchResultRegistered(
  [
    { ...base, registered: true, registered_item_id: itemId },
    {
      ...base,
      tmdb_id: 872585,
      media_type: "tv",
      title: "TV Same Id",
      registered: true,
      registered_item_id: "22222222-2222-2222-2222-222222222222",
    },
  ],
  "movie",
  872585,
  itemId,
);
const unmarkMovieOnly = patchSearchResultUnregistered(sameIdTv, "movie", 872585);
assert(unmarkMovieOnly[0].registered === false, "movie unregistered");
assert(unmarkMovieOnly[1].registered === true, "tv with same numeric id stays registered");
assert(unmarkMovieOnly[1].media_type === "tv", "tv media_type preserved");

assert(
  parseTmdbIdentityFromDeletedItem({
    id: itemId,
    external_source: null,
    external_media_type: null,
    external_id: null,
  }) === null,
  "legacy item without external identity is ignored",
);

const snapshot = {
  queryInput: "오펜",
  appliedQuery: "오펜",
  mediaType: "movie",
  page: 1,
  status: null,
  results: patched,
  upstreamTotalPages: 1,
  upstreamTotalResults: 1,
  hasSearched: true,
};
const nextSnap = unmarkDeletedItemInSearchSnapshot(snapshot, {
  id: itemId,
  external_source: "tmdb",
  external_media_type: "movie",
  external_id: "872585",
});
assert(nextSnap !== snapshot, "snapshot replaced after tmdb delete");
assert(nextSnap.results[0].registered === false, "snapshot row unregistered");
assert(nextSnap.results[0].registered_item_id === null, "snapshot item id cleared");

const legacySnap = unmarkDeletedItemInSearchSnapshot(snapshot, {
  id: itemId,
  external_source: null,
  external_media_type: null,
  external_id: null,
});
assert(legacySnap === snapshot, "legacy delete leaves snapshot untouched");

console.log("verify-tmdb-search-registration: ok");
