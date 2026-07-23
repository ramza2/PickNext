/**
 * Item POST/PATCH API client checks (no Frontend test framework).
 * Run: node scripts/verify-item-write-api.mjs
 */
import assert from "node:assert/strict";

const API_BASE = "/api/v1";

function joinUrl(base, path) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${base}${normalizedPath}`;
}

class ApiError extends Error {
  constructor(status, message, detail) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function apiRequest(path, options) {
  const headers = new Headers(options?.headers);
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }
  if (options?.body != null && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(joinUrl(API_BASE, path), {
    ...options,
    headers,
  });

  if (response.ok) {
    if (response.status === 204) {
      return undefined;
    }
    return response.json();
  }

  throw new ApiError(response.status, `Request failed (${response.status})`);
}

async function createItem(payload) {
  return apiRequest("/items", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function updateItem(itemId, payload) {
  return apiRequest(`/items/${encodeURIComponent(itemId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

async function deleteItem(itemId) {
  return apiRequest(`/items/${encodeURIComponent(itemId)}`, {
    method: "DELETE",
  });
}

async function createCollection(payload) {
  return apiRequest("/collections", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function updateCollection(collectionId, payload) {
  return apiRequest(`/collections/${encodeURIComponent(collectionId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

async function deleteCollection(collectionId) {
  return apiRequest(`/collections/${encodeURIComponent(collectionId)}`, {
    method: "DELETE",
  });
}

async function getItem(itemId) {
  return apiRequest(`/items/${encodeURIComponent(itemId)}`);
}

function buildItemUpdatePayload(values, source) {
  const payload = {};
  const title = values.title.trim();
  const progressNote = values.progressNote.trim() || null;
  const memo = values.memo.trim() || null;
  const sourceCollectionId = source.collection?.id ?? null;

  if (title !== source.title) payload.title = title;
  if (values.categoryId !== source.category.id) {
    payload.category_id = values.categoryId;
  }
  if (values.collectionId !== sourceCollectionId) {
    payload.collection_id = values.collectionId;
  }
  if (values.status !== source.status) payload.status = values.status;
  if (values.rating !== source.rating) payload.rating = values.rating;
  if (progressNote !== source.progress_note) {
    payload.progress_note = progressNote;
  }
  if (memo !== source.memo) payload.memo = memo;
  return payload;
}

let lastUrl;
let lastInit;
let jsonCalled = false;
let nextStatus = 201;
let nextJson = {
  id: "item-new",
  title: "스타워즈",
  status: "PLANNED",
  rating: 0,
  progress_note: null,
  memo: null,
  category: { id: "cat-1", name: "영화" },
  collection: null,
  created_at: "2026-07-22T00:00:00+00:00",
  updated_at: "2026-07-22T00:00:00+00:00",
};

globalThis.fetch = async (url, init) => {
  lastUrl = url;
  lastInit = init;
  jsonCalled = false;
  return {
    ok: nextStatus >= 200 && nextStatus < 300,
    status: nextStatus,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => {
      jsonCalled = true;
      return nextJson;
    },
  };
};

nextStatus = 201;
const created = await createItem({
  title: "스타워즈",
  category_id: "cat-1",
  collection_id: null,
  status: "PLANNED",
  rating: 0,
  progress_note: null,
  memo: null,
});
assert.equal(lastInit.method, "POST");
assert.match(lastUrl, /\/api\/v1\/items$/);
assert.equal(lastInit.headers.get("Content-Type"), "application/json");
const createBody = JSON.parse(lastInit.body);
assert.equal(createBody.title, "스타워즈");
assert.equal(createBody.category_id, "cat-1");
assert.equal(createBody.collection_id, null);
assert.equal(jsonCalled, true);
assert.equal(created.id, "item-new");

nextStatus = 404;
await assert.rejects(createItem({ title: "x", category_id: "missing" }), (err) => {
  assert.equal(err.status, 404);
  return true;
});

nextStatus = 409;
await assert.rejects(createItem({ title: "x", category_id: "cat-1" }), (err) => {
  assert.equal(err.status, 409);
  return true;
});

nextStatus = 422;
await assert.rejects(createItem({ title: "", category_id: "cat-1" }), (err) => {
  assert.equal(err.status, 422);
  return true;
});

nextStatus = 200;
nextJson = {
  id: "item/id",
  title: "변경",
  status: "COMPLETED",
  rating: 4.5,
  progress_note: null,
  memo: null,
  category: { id: "cat-1", name: "영화" },
  collection: { id: "col-1", name: "시리즈" },
  created_at: "2026-07-22T00:00:00+00:00",
  updated_at: "2026-07-22T01:00:00+00:00",
};
const updated = await updateItem("item/id", {
  title: "변경",
  collection_id: null,
  progress_note: null,
  memo: null,
});
assert.equal(lastInit.method, "PATCH");
assert.match(lastUrl, /\/api\/v1\/items\/item%2Fid$/);
const patchBody = JSON.parse(lastInit.body);
assert.equal(patchBody.title, "변경");
assert.equal(patchBody.collection_id, null);
assert.equal(patchBody.progress_note, null);
assert.equal(patchBody.memo, null);
assert.equal("undefined" in patchBody, false);
assert.equal(updated.title, "변경");

const source = {
  title: "기존",
  status: "PLANNED",
  rating: 0,
  progress_note: "노트",
  memo: "메모",
  category: { id: "cat-1", name: "영화" },
  collection: { id: "col-1", name: "A" },
};
const samePayload = buildItemUpdatePayload(
  {
    title: "  기존  ",
    categoryId: "cat-1",
    collectionId: "col-1",
    status: "PLANNED",
    rating: 0,
    progressNote: "노트",
    memo: "메모",
  },
  source,
);
assert.deepEqual(samePayload, {});

const changedPayload = buildItemUpdatePayload(
  {
    title: "새제목",
    categoryId: "cat-1",
    collectionId: null,
    status: "COMPLETED",
    rating: 1,
    progressNote: "  ",
    memo: "  ",
  },
  source,
);
assert.equal(changedPayload.title, "새제목");
assert.equal(changedPayload.collection_id, null);
assert.equal(changedPayload.status, "COMPLETED");
assert.equal(changedPayload.rating, 1);
assert.equal(changedPayload.progress_note, null);
assert.equal(changedPayload.memo, null);
assert.equal("category_id" in changedPayload, false);

nextStatus = 404;
await assert.rejects(updateItem("missing", { title: "x" }), (err) => {
  assert.equal(err.status, 404);
  return true;
});

nextStatus = 409;
await assert.rejects(updateItem("busy", { title: "x" }), (err) => {
  assert.equal(err.status, 409);
  return true;
});

nextStatus = 422;
await assert.rejects(updateItem("bad", { title: "x" }), (err) => {
  assert.equal(err.status, 422);
  return true;
});

nextStatus = 204;
const deleted = await deleteItem("item-1");
assert.equal(deleted, undefined);
assert.equal(jsonCalled, false);

nextStatus = 201;
nextJson = {
  id: "col-new",
  name: "컬렉션",
  item_count: 0,
  planned_count: 0,
  completed_count: 0,
  categories: [],
  created_at: "2026-07-22T00:00:00+00:00",
  updated_at: "2026-07-22T00:00:00+00:00",
};
await createCollection({ name: "컬렉션" });
assert.equal(lastInit.method, "POST");

nextStatus = 200;
await updateCollection("col/id", { name: "이름" });
assert.equal(lastInit.method, "PATCH");

nextStatus = 204;
await deleteCollection("col-empty");
assert.equal(jsonCalled, false);

nextStatus = 200;
nextJson = {
  id: "item-1",
  title: "상세",
  status: "PLANNED",
  rating: 0,
  progress_note: null,
  memo: null,
  category: { id: "cat-1", name: "영화" },
  collection: null,
  created_at: "2026-07-22T00:00:00+00:00",
  updated_at: "2026-07-22T00:00:00+00:00",
};
const detail = await getItem("item-1");
assert.equal(detail.id, "item-1");
assert.equal(jsonCalled, true);

console.log("verify-item-write-api: ok");
