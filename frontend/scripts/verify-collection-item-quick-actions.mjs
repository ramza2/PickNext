/**
 * Collection Item quick actions (unlink / status) client checks.
 * Run: node scripts/verify-collection-item-quick-actions.mjs
 */
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const API_BASE = "/api/v1";

function joinUrl(base, pathName) {
  const normalizedPath = pathName.startsWith("/") ? pathName : `/${pathName}`;
  return `${base}${normalizedPath}`;
}

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function apiRequest(pathName, options) {
  const headers = new Headers(options?.headers);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  if (options?.body != null && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(joinUrl(API_BASE, pathName), {
    ...options,
    headers,
  });
  if (response.ok) {
    if (response.status === 204) return undefined;
    return response.json();
  }
  throw new ApiError(response.status, `Request failed (${response.status})`);
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

async function deleteCollection(collectionId) {
  return apiRequest(`/collections/${encodeURIComponent(collectionId)}`, {
    method: "DELETE",
  });
}

let lastUrl;
let lastInit;
let jsonCalled = false;
let nextStatus = 200;
let nextJson = {
  id: "item/id",
  title: "스타워즈",
  status: "PLANNED",
  rating: 0,
  progress_note: null,
  memo: null,
  category: { id: "cat-1", name: "영화" },
  collection: null,
  created_at: "2026-07-23T00:00:00+00:00",
  updated_at: "2026-07-23T00:00:00+00:00",
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

nextStatus = 200;
const unlinked = await updateItem("item/id", { collection_id: null });
assert.equal(lastInit.method, "PATCH");
assert.match(lastUrl, /\/api\/v1\/items\/item%2Fid$/);
assert.deepEqual(JSON.parse(lastInit.body), { collection_id: null });
assert.equal(jsonCalled, true);
assert.equal(unlinked.collection, null);

nextStatus = 200;
nextJson = { ...nextJson, status: "COMPLETED", collection: { id: "col-1", name: "시리즈" } };
const completed = await updateItem("item/id", { status: "COMPLETED" });
assert.deepEqual(JSON.parse(lastInit.body), { status: "COMPLETED" });
assert.equal(completed.status, "COMPLETED");

nextStatus = 404;
await assert.rejects(updateItem("missing", { collection_id: null }), (err) => {
  assert.equal(err.status, 404);
  return true;
});

nextStatus = 409;
await assert.rejects(updateItem("busy", { collection_id: null }), (err) => {
  assert.equal(err.status, 409);
  return true;
});

nextStatus = 422;
await assert.rejects(updateItem("bad", { collection_id: null }), (err) => {
  assert.equal(err.status, 422);
  return true;
});

nextStatus = 204;
const deleted = await deleteItem("item-1");
assert.equal(deleted, undefined);
assert.equal(jsonCalled, false);
assert.equal(lastInit.method, "DELETE");

nextStatus = 204;
await deleteCollection("col-empty");
assert.equal(lastInit.method, "DELETE");

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const app = fs.readFileSync(path.join(root, "src/app/App.tsx"), "utf8");
const messages = fs.readFileSync(
  path.join(root, "src/api/itemWriteMessages.ts"),
  "utf8",
);

assert.match(app, /collection_id:\s*null/);
assert.match(app, /컬렉션에서 항목 제거/);
assert.match(app, /handleUnlinkConfirm/);
assert.match(app, /handleQuickStatusToggle/);
assert.match(messages, /itemUnlinkSuccessToast/);
assert.match(messages, /buildCollectionUnlinkConfirmBody/);

const unlinkIdx = app.indexOf("handleUnlinkConfirm");
assert.ok(unlinkIdx > 0);
const unlinkWindow = app.slice(unlinkIdx, unlinkIdx + 1200);
assert.match(unlinkWindow, /updateItem\(/);
assert.doesNotMatch(unlinkWindow, /deleteItem\(/);
assert.doesNotMatch(unlinkWindow, /deleteCollection\(/);

assert.match(app, /deleteItem\(/);
assert.match(app, /deleteCollection\(/);
assert.match(app, /항목을 삭제합니다/);

console.log("verify-collection-item-quick-actions: ok");
