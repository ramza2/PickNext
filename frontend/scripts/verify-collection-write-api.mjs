/**
 * Collection POST/PATCH API client checks (no Frontend test framework).
 * Run: node scripts/verify-collection-write-api.mjs
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

async function deleteItem(itemId) {
  return apiRequest(`/items/${encodeURIComponent(itemId)}`, {
    method: "DELETE",
  });
}

let lastUrl;
let lastInit;
let jsonCalled = false;
let jsonBody = null;
let nextStatus = 201;
let nextJson = {
  id: "col-new",
  name: "스타워즈",
  item_count: 0,
  planned_count: 0,
  completed_count: 0,
  categories: [],
  created_at: "2026-07-22T00:00:00+00:00",
  updated_at: "2026-07-22T00:00:00+00:00",
};

globalThis.fetch = async (url, init) => {
  lastUrl = url;
  lastInit = init;
  jsonCalled = false;
  jsonBody = null;
  return {
    ok: nextStatus >= 200 && nextStatus < 300,
    status: nextStatus,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => {
      jsonCalled = true;
      jsonBody = nextJson;
      return nextJson;
    },
  };
};

nextStatus = 201;
nextJson = {
  id: "col-new",
  name: "새 컬렉션",
  item_count: 0,
  planned_count: 0,
  completed_count: 0,
  categories: [],
  created_at: "2026-07-22T00:00:00+00:00",
  updated_at: "2026-07-22T00:00:00+00:00",
};
const created = await createCollection({ name: "새 컬렉션" });
assert.equal(lastInit.method, "POST");
assert.match(lastUrl, /\/api\/v1\/collections$/);
assert.equal(lastInit.headers.get("Content-Type"), "application/json");
assert.equal(JSON.parse(lastInit.body).name, "새 컬렉션");
assert.equal(jsonCalled, true);
assert.equal(created.id, "col-new");
assert.equal(created.item_count, 0);

nextStatus = 409;
await assert.rejects(createCollection({ name: "중복" }), (err) => {
  assert.equal(err.status, 409);
  return true;
});

nextStatus = 422;
await assert.rejects(createCollection({ name: "" }), (err) => {
  assert.equal(err.status, 422);
  return true;
});

nextStatus = 200;
nextJson = {
  id: "col/id",
  name: "변경 이름",
  item_count: 3,
  planned_count: 2,
  completed_count: 1,
  categories: [{ id: "cat-1", name: "영화", item_count: 3 }],
  created_at: "2026-07-22T00:00:00+00:00",
  updated_at: "2026-07-22T01:00:00+00:00",
};
const updated = await updateCollection("col/id", { name: "변경 이름" });
assert.equal(lastInit.method, "PATCH");
assert.match(lastUrl, /\/api\/v1\/collections\/col%2Fid$/);
assert.equal(JSON.parse(lastInit.body).name, "변경 이름");
assert.equal(updated.name, "변경 이름");
assert.equal(updated.item_count, 3);

nextStatus = 404;
await assert.rejects(updateCollection("missing", { name: "x" }), (err) => {
  assert.equal(err.status, 404);
  return true;
});

nextStatus = 409;
await assert.rejects(updateCollection("busy", { name: "x" }), (err) => {
  assert.equal(err.status, 409);
  return true;
});

nextStatus = 422;
await assert.rejects(updateCollection("bad", { name: "x" }), (err) => {
  assert.equal(err.status, 422);
  return true;
});

nextStatus = 204;
const deleted = await deleteCollection("col-empty");
assert.equal(deleted, undefined);
assert.equal(jsonCalled, false);

nextStatus = 204;
const itemDeleted = await deleteItem("item-1");
assert.equal(itemDeleted, undefined);
assert.equal(jsonCalled, false);

console.log("verify-collection-write-api: ok");
